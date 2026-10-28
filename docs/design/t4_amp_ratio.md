# T4 — the amplitude ratio: both operands are banked, and the missing piece is the bar they must agree within

Arithmetic on banked arrays only. No solve, no gate run, no field reconstruction.

## 1. Result

| quantity | value | source |
|---|---|---|
| `sum(A_ez^2)` | 3.036149093425e+02 / 15276 pts, rms 1.409797455137e-01 | `out/c1_spectrum.npz:A_ez` (201,76) |
| `sum(A_ey^2)` | 1.080440832223e+02 / 15400 pts, rms 8.376066833477e-02 | `out/c1_spectrum.npz:A_ey` (200,77) |
| **`R_analytic`** | **2.810102138752** | quotient of the rows above |
| `R_analytic`, per-sample | 2.832912603875 | `mean/sq`, n-gap 15400/15276 = 1.008118 |
| amplitude ratio | 1.676336 (per-sample 1.683126) | `sqrt` of both |

`A_ez = PANA.e_z` on y(nodes)×z(cells), `A_ey = PANA.e_y` on y(cells)×z(nodes) (`c1_audit.py:593-594`, guard `:600-602`, banked `:871`). Both arrays are **array-identical** (`np.array_equal` = True) between `c1_spectrum.npz` and `pecbox_spectrum.npz` — the two files are not byte-identical, they differ everywhere else — so `R_analytic` is one number and cannot separate the PMC leg (col 738) from the PEC leg (col 699). The extracted side can: it is banked as a scalar, `R_extracted = 4.0489791163982565`, which is `1.440865×` `R_analytic`, and §2 is now about the column it was taken on.

## 2. The artefacts, named: `R_extracted` is banked, the arrays behind it are not

Both readings are in the two captures (`tools/host/c1-audit/out/` — the `out/` of §1's table is relative to that directory), and the arrays that formed the second one are still not saved. `c1_spectrum.npz` (16,972,501 bytes): `lam` (1444,), `j = [738]`, `bank_col` 738, `R_extracted` 4.0489791163982565, `beta` 312.78276463, `corr_ey` 0.92077078, `corr_ez_vv` 0.93528673, `A_ez` (201,76), `A_ey` (200,77), `ok` [True]. `pecbox_spectrum.npz` (15,568,904 bytes): `lam` (1382,), `j = [699, 704]`, `bank_col` 738, `R_extracted` 70.635018555128326, `beta` [311.77211206, 86.93931629], `corr_ey` [0.91234304, −0.42641899], `corr_ez_vv` [0.93692972, −0.08313435], `ok` [True, False]. What is **not** banked is the pair the scalar was reduced from: `c1_audit.py:679-680` builds `e_y = e_at(_ey_pts)[:,:,0]*CELL`, `:686-687` builds `e_z_vv = e_at(_ezc_pts)[:,:,1]*CELL`, `:705` reduces each to a scalar, and `:816` banks only `A_ez`, `A_ey` and scalars (keys at `:840-871`). `.scratch/e_z_signed_41x22.npz` does not hold them either: `e_z_raw`/`e_z_plane` are **longitudinal** (`-interp(beta*z_free)`, `c @ z_free`), not the vertical one.

Not one script's oversight: every artefact that pairs the two fields normalises each by its own norm first — `c1_audit.py:694-695` (correlation), `.scratch/d22_t3_regions.py:69-74` (`_unit_pair`: `A/|A|`, `E/|E|`) — so the amplitude ratio is divided out by construction wherever the pair was analysed. The record says the same at `decisions.md:7956`: "What the true vertical-over-in-plane energy ratio is has not been computed." *`decisions.md:7956` is the pre-extraction record; the banks are ahead of it, they do not contradict it: the ratio is banked as a scalar, the fields behind it are not.* What remains open is the **column**: 738 (the peak, `ok` True) gives 4.0489791163982565, 704 (the last leg scanned, `ok` False) gives 70.635018555128326 — a factor 17.445142719817547. A ratio quoted without its column is not a measurement, and §9 makes recording it a precondition of scoring. Two points are inference rather than record and are marked so: that 70.635 belongs to column 704 (the PEC file's own `bank_col` is 738, so the attribution rests on `j = [699, 704]` beside `ok = [True, False]`), and that `R_extracted` was formed at run time from the un-reduced fields rather than from the banked arrays (forced, since `A_ez`/`A_ey` are array-identical across the two files while their `R_extracted` differ by 17×). Neither needs a re-run to settle the gate.

**Where the PEC number comes from, and what identifies the mode.** The PEC leg's quotable ratio is `R = 4.163656524825077`, the ratio of the column the solver selects, 699 (`ok` `True`, `corr_ey` 0.91234304, `corr_ez_vv` 0.93692972). The `70.635018555128326` read out of `pecbox_spectrum.npz` above is the ratio of the last *scanned* column, 704, whose leg is the failing witness; that capture was not overwritten when the selection defect was fixed, so the stale scalar deliberately survives in it (`c1_audit.py:210-213`). The correction is a re-read of the same banked run, not a new measurement, and it is the same lesson the ladder met from the other end: **the column index of the physical mode is environment-dependent.** The banked `c1_spectrum.npz` names 738 for this mode while a fresh solve of the identical rung-0 mesh names 732, with `R` agreeing to 8e-13 (§12.1); on the PEC box the same solver names 699. Neither 699, 704, 732 nor 738 is a durable name for the mode, and that ambiguity is exactly what produced `70.635` here. The mode is identified by `beta_sq` and by `R`, and a ratio is quoted with both.

## 3. The nearest pair that *is* banked, labelled a different object

`.scratch/tol/logs/TOLFLUX_planes.npz`: FDTD tone blocks `plane_Ez` (9,201,76), `plane_Ey` (9,200,77), `plane_f` 7.833566197718e+09, `plane_n_samples` 6026. Pooled `sum|Ez|^2/sum|Ey|^2` = **3.439935** (per-sample 3.467858), per station 3.101484 → 3.620866. It is a time-domain plane capture at one tone, not the eigenvector extraction, so it is **not** `R_extracted` and is not substituted for it. It places the analytic plane mode 18.3 % below the FDTD plane ratio (1 − 2.810102/3.439935). Both readings are 2.8–3.4: vertical/in-plane is order three, **not** the "roughly 10x" that opened the hunt, and not 0.0272.

## 4. Why 0.0272 is not this ratio

2.810102/0.0272240 = **103.2** — different quantity at any normalisation. The 0.0272 numerator is `-|beta*z_free|` (**longitudinal**) over `sum(e_y_unit^2)` (**in-plane**): `tools/corr_ez_101_20.py:424, :456, :75`, `decisions.md:7952-7954` (whose text says the vertical extracted component "appears nowhere in it"). A vertical-over-in-plane expectation does not apply to it.

## 5. What the 2.85x / 2.89x denominator is

`excess = (region share of the deficit) / sqrt(A-share × E-share)` — `.scratch/d22_t3_regions.py:104-105`, read-out `:195-197`. The denominator is the **geometric mean of the region's analytic-energy share and its extracted-energy share** — not its energy share alone and not the total energy. Dimensionless; 1.0 = residual spread in proportion to the field. Recomputed from `decisions.md:7962-7966`: fringe 0.570/sqrt(0.1474×0.2716) = 2.849 (PMC 2.85); under strip 0.391/sqrt(0.8222×0.6780) = 0.524 (0.52); outer 0.039/sqrt(0.0304×0.0504) = 0.997 (1.01). So 2.85x/2.89x are **deficit-localisation ratios on the `A_ez`/`e_z_vv` pair**, not amplitude ratios.

## 6. T2: `beta_fit` versus `beta_eigen`

`T2_TOL = 0.005` (`tools/gates_101_20.py:166`); `T2_agree` (`:544-560`) is `|beta_fit − beta_eig|/|beta_eig| <= tol`, route 2 read from the capture's `beta`. `beta_eigen = 312.7827646322591` (= `c1_spectrum.npz:beta`, col 738), `beta_fit = 326.9107654423116` → **4.516873 %** (4.321669 % on the fit) = **9.03x** the tolerance: FAIL, and the docstring calls that intended. The beta `TOLFLUX.json` carries, 314.03158662735785, is **0.399262 %** above `beta_eigen` — inside 0.005 with 1.25x margin. Two fits sit at 4.52 % and 0.40 % of the same eigenvalue; §7 is why the gate reaches neither.

## 7. Why `beta` is shape `(0,)`

`TOLFLUX_planes.npz` is the **tone** plane dump: `emfit/studies.py:3242-3246` writes it for `excite != "pulse"` with `freqs=np.empty(0)`, `spectra=np.empty((0, spec.size))` — "a tone has no bins to store: the sweep half of the record is empty". Every frequency-indexed key (`f`, `beta`, `s11*`, `s21*`, `passivity*`, `refused`, `v`, `i`, `z0`) is `(0,)` for that reason alone; the nine station blocks are real. So the zeros do not mean "a capture without beta" — the beta exists, in `TOLFLUX.json`. `T2_agree`'s `ValueError` (`decisions.md:7226`) is honest, but its stated cause is not the mechanism: it reads a dump whose sweep half is empty by design and never looks at the json.

## 8. Record against brief

- `4.52 %` = (326.9107654423116 − 312.7827646322591)/312.7827646322591 = 4.5169 %: the rounded record figure is right, and the 45x remark against the old 1e-3 is 45.2x.
- `4.52` hits: `decisions.md:7196` (b.5 first record), `:7224` (c.2, ~45x below), `:7371`/`:7375` (§(g) re-scope, T2 fails intended), `:7680` (estimator span 6.24 %), `:7716` ("at most about one third"); `:1219` is an unrelated 24.525 s timing.
- `2.85x`/`2.89x`, `57.0 %`/`57.9 %` reproduce exactly (PMC col 738 / PEC col 699).
- **Miscite:** `decisions.md:7948` puts the `e_z_vv` read at `c1_audit.py:510-511`; the construction is `:686-687`.
- **Duplicate captures:** `TOLFLUX.json` and `TOL.json` carry identical `beta`/ephemera but differ on `poynting` (True/False) and `wall` (4210.48/4560.05).
- **Open tension, unresolved here:** 4.52 % (fail by 9x) and 0.40 % (pass) are both "beta against 312.7827646322591". Which fit T2 is scored on is not settled by the banks; naming the estimator is a precondition, as `decisions.md:7680` already warns.

## 9. `T4_amp`: the pass condition it will have to be scored against (registered, not implemented)

**Registered, not implemented.** The bar has a ruling of record — §9.2 is ADOPTED and LOCKED and the entry is in `decisions.md` — so `T4_amp` is no longer a proposal. Nothing in this section is enforced: no `.py` file compares `R_extracted` against `tol_rel`, no gate entry appears, and `m3c_gate_v2.md:630` still reads "Seven entries, no more." The section fixes what `T4_amp` asserts, and what it must establish before it is allowed to assert it. The bar is **a pre-registered engineering requirement, not a derived error budget** — nothing in the record measures the scatter of `R_extracted` on this design, so nothing in the record can derive a tolerance from it.

### 9.1 The scored quantity

`Q = R_extracted / R_analytic`, scored as the inequality `|Q − 1| <= tol_rel`, with both operands read from the banks: `R_analytic = 2.810102138752` (§1, `sum(A_ez^2)/sum(A_ey^2)`, one number because the two arrays are array-identical across the captures) and `R_extracted = 4.0489791163982565` from the **PMC leg, column 738**, whose `ok` is `True` and whose capture's `bank_col` is 738. Today `Q = 1.440865461991999`.

- **The PMC leg is the scored leg.** Column 738 is the peak column of `c1_spectrum.npz` (`j = [738]`, `ok = [True]`) and the column §6/§7 read `beta` on (`beta_eigen = 312.7827646322591`), so scoring and the beta record sit on the same column.
- **The PEC leg is excluded from scoring; what is excluded is the banked scalar, not the leg.** The leg's own ratio is `R = 4.163656524825077`, at its identified column 699 (§2). What `pecbox_spectrum.npz` carries under `R_extracted` is 70.635018555128326, the last *scanned* column (704, the failing witness), and it is 17.445142719817547× the peak-column value — the stored scalar is the wrong-column artefact. The leg is not a second physics result to be compared with the PMC one: its leg list is `j = [699, 704]` with `ok = [True, False]` and its own `bank_col` is 738, inherited through the PMC path. It is retained as the diagnostic of column sensitivity in §9.4, and not as a data point. Arithmetic only, not a second measurement: `4.163656524825077 / 2.8101021387524523 = 1.4816744442867605`, an error of 48.167 % against the ±10 % band, so the PEC leg read at its own column would also fail the bar — it is excluded for provenance and for leg count, not because re-reading it rescues the verdict. *Inference, marked as inference:* attributing 70.635 to column 704 rests on the leg list beside `ok`, not on the file's `bank_col`.
- **n = 1.** One capture per leg, one column, one run. There is no empirical scatter in the record for this quantity, and none is assumed below.

### 9.2 The bar: ±10 % relative on `Q` — ADOPTED and LOCKED

**Adopted.** `T4_amp`'s pass condition is `|Q − 1| <= 0.10` on the scored quantity `Q = R_extracted / R_analytic`, equivalently `0.90 <= Q <= 1.10`. **The band is defined on the dimensionless ratio `Q`; the interval it implies on the operand is a consequence of that definition, not a second and separate bar.**

On the operand, with `R_analytic = 2.8101021387524523`, the adopted band requires `R_extracted ∈ [2.52909192487721, 3.09111235262770]` — `0.90 × R_analytic` to `1.10 × R_analytic`, converted in Python from the banked number rather than by hand. The interval is quoted so that a new `R_extracted` can be scored without re-deriving the division; it carries no independent authority, and if `R_analytic` is ever re-measured the interval moves with it while the band does not.

**Status today: FAIL.** `Q = 1.440865461991999` — `R_extracted = 4.0489791163982565` (PMC leg, peak column 738) over `R_analytic = 2.8101021387524523` — a relative error of `44.086546199199894 %`, which is `4.408654619919989×` the `±10 %` half-width. The extraction is over the limit by a factor of `4.408654619919989`.

"Over the limit" below is `|Q − 1| / half-width`: 0 is exact agreement, 1.00 sits exactly on the limit, anything above 1.00 fails.

| bar | pass band on `Q` | pass band on `R_extracted` | half-width as % of `R_analytic` | `\|Q − 1\|` / half-width today | today |
|---|---|---|---|---|---|
| **±10 % relative — ADOPTED and LOCKED** | [0.90, 1.10] | [2.52909192487721, 3.09111235262770] | 10.000 % | **4.408654619919989×** | **FAIL** |
| ±20 % relative — rejected | [0.80, 1.20] | [2.24808171100196, 3.37212256650294] | 20.000 % | 2.2043273099599947× | FAIL |
| ±25 % relative — rejected | [0.75, 1.25] | [2.10757660406434, 3.51262767344057] | 25.000 % | 1.7634618479679958× | FAIL |
| ±0.2 absolute, on the ratio — rejected | [0.9288282097501301, 1.0711717902498699] | [2.61010213875245, 3.01010213875245] | 7.117179024986979 % | 6.1943848882290204× | FAIL |

**The two relative alternatives were rejected as too loose to constitute a test.** `±25 %` still fails today, but only by `1.7634618479679958×` the half-width — close enough that a small numerical tweak could flip the verdict without the underlying extraction having been fixed, and **a bar that a tweak can accidentally satisfy measures nothing**. `±20 %` fails by `2.2043273099599947×` for the same reason in weaker form. Neither would test the physics: both would report PASS on a run whose ratio had moved for reasons unrelated to the divergence the clause exists to detect.

**`±0.2` absolute was rejected on two counts.** It is **not** the looser option it reads as: `0.2` is `7.117179024986979 %` of `R_analytic = 2.810102138752`, i.e. **tighter** than the adopted `±10 %`, and the two bands coincide only where `R_analytic = 2.0` — which is why its row above fails by `6.1943848882290204×` rather than `4.408654619919989×`. And a tolerance on a ratio should be relative, so that it scales with the physical quantity instead of being pinned to one particular lattice.

**Why `±10 %` itself.** It is a real test: today's reading fails it by `4.408654619919989×`, so satisfying it requires the physics to improve rather than the bookkeeping to shift. And `10 %` is the standard engineering target for a 2D cross-section extraction — small enough that agreement at that level is evidence the extraction is right, loose enough that a converged method is not failed on discretisation noise alone.

**Locked.** The bar was registered before any measurement was taken on the refined mesh, and **it is not to be moved after the measurement**: bar first, number second, verdict third. That ordering is the whole of its value — a tolerance chosen after seeing the number describes the result it was meant to judge. Any change is governed by §9.6, which requires a pre-registered revisit naming a mechanism, not a new number. The measurement the lock was set ahead of has now been taken, and it is recorded in §9.7: it does not move the bar and it does not move the verdict.

### 9.3 Why relative rather than absolute

`Q` is dimensionless and both operands scale together with drive level, meshing bookkeeping and normalisation, so a relative band is scale-free and survives being carried to a re-meshed or re-scaled run, whereas ±0.2 absolute is a statement about `R_analytic = 2.810102138752` — a number set by a 201×76 vertical over a 200×77 in-plane cell count — and would silently harden or loosen under any change of grid or geometry. The trade-off is real and is not hidden: at this geometry the relative bar is the wider of the two (±10 % of 2.810102138752 is ±0.281 in the ratio's units, against the ±0.2 of the absolute row, and the two coincide only near `R_analytic = 2.0`), so "relative" here is a choice of a band that moves with the quantity, not a way of buying margin. Relative is chosen because the object being scored is the ratio itself, and because it is the form that does not need re-deriving whenever the grid changes.

### 9.4 Precondition: the column must be recorded, and asserted to be the peak

`R_extracted` is knife-edge sensitive to the column it is read on — 4.0489791163982565 at 738 against 70.635018555128326 at 704, a factor 17.445142719817547, because the extraction reduces per column and column 704 is a non-carrier (`ok` False); the identified PEC column 699 gives 4.163656524825077 (§2), so the 17× spread is between a carrier and a non-carrier column and not between the two legs — read at their own identified columns the two legs differ by `4.163656524825077 / 4.0489791163982565 = 1.0283225487536798`, i.e. 2.8 %. A bar applied to a number that can move by 17× on a selection the record does not pin down is not a test of anything. So `T4_amp` will require, before it compares anything:

1. the column actually used is written into the run record, and
2. that column is asserted to **be** the peak column — the leg's `ok` is `True` and the column equals the capture's `bank_col` — with a mismatch failing closed rather than being scored.

§6 and §7 are the precedent for what happens without this rule, and both are already in this document. §6 has two fits to the same eigenvalue — 4.516873 % away (T2 = 9.03× FAIL) and 0.399262 % away (1.25× margin, PASS) — and no bank says which of the two T2 reads: "naming the estimator is a precondition" (`decisions.md:7680`), still unresolved, carried as the open tension in §8. §7 is the same failure mode reached from the other side: `beta` is shape `(0,)` not because there is no `beta` but because the tone dump writes `freqs=np.empty(0)` (`emfit/studies.py:3242-3246`), so a key can be present, correctly shaped, empty, and still read as a measurement. Column selection is the `T4_amp` instance of both: a gate that reads the wrong column, or an empty one, returns a number rather than the physics.

### 9.5 What pass and fail will mean

**PASS** — `|R_extracted/R_analytic − 1| <= 0.10` on the peak column — will mean the extracted vertical-over-in-plane energy ratio agrees with the analytic one inside the requirement that was set for it in advance. It will not mean the extraction is right: it is one necessary condition on one number at n = 1.

**FAIL** is where the record stands today. `Q = 1.440865461991999` misses ±10 % by 4.408654619919989× the half-width (44.086546199199894 % against 10 %), and misses even ±25 % by 1.7634618479679958×. Stated here so the bar is not later mistaken for a description of the measurement.

The bar is **a pre-registered engineering requirement, not a derived error budget**: no part of this document estimates what the disagreement *ought* to be, and with n = 1 and no empirical scatter there is nothing to derive one from — a "derived" tolerance would be a number chosen first and described as measured afterwards.

**Registered, not implemented.** The bar is registered and nothing enforces it: no `.py` file compares `R_extracted` against `tol_rel`, no gate entry appears, and `m3c_gate_v2.md:630` still reads "Seven entries, no more."; when `T4_amp` is implemented as a gate entry it becomes the eighth, and that line must be edited deliberately, as a separate act.

### 9.6 Revisit clause

The bar may be revisited **once**. The revisit must be pre-registered in `decisions.md` — the new tolerance, the mechanism that justifies it, and the date — *before* it is applied to any computed value. It must never be tuned post-hoc to a number already in hand: choosing the tolerance after seeing 1.4409 (or 1.763, or 6.194) converts the gate into a description of the result it was supposed to judge. A revisit prompted by a measured miss must therefore name a mechanism — a changed column-selection rule, a re-meshed run (which §9.7 now excludes at the strip band: a 3× refinement there moved the operand by 0.13 %, so a re-mesh can be named only at the z band or the air band), a different leg, a resolved estimator question from §6 — and not merely a new number.

### 9.7 The measurement the bar was locked ahead of: the strip band is refined to flatness and the verdict does not move

**Ordering.** §9.2’s bar was registered and committed before any refined-mesh solve had been run; this section is that measurement, taken afterwards and reported against a bar it did not choose. Bar first, number second, verdict third — nothing in §9.2 was touched to produce §9.7.

**The experiment.** Strip-band cells alone: `C1_STRIP_CELLS` = 12 / 18 / 24 / 36 against the banked 12, with the 9|9 air grading and the 8|4|4 substrate held fixed at their banked values — a one-parameter family in which the strip is the only thing that moves. The knob lives in `tools/host/c1-audit/c1_audit.py` (default 12 = banked mesh, guarded `>= 1`, echoed into the run’s `mesh :` provenance line) alongside `C1_OUTDIR` and `C1_ALLOW_REMESH`; with them unset, the mesh, both output paths, both `SystemExit` messages and the reproduction target are byte-identical to before, and `C1_STRIP_CELLS=12` reproduces the banked capture to 10 digits — `best_col` 738, `corr_e_y` 0.92077078481114194, `R_extracted` 4.0489791164, REPRO PASS.

| strip cells | mesh (nodes) | strip cell size | `R_extracted` | `Q` | relative error | beta | eps_eff | column |
|---|---|---|---|---|---|---|---|---|
| 12 | 31x17 | 250.000 um | 4.0489791164 | 1.4408654620 | 44.0865 % | 312.782764632 | 3.629512208 | 738 |
| 18 | 37x17 | 166.667 um | 4.0463369445 | 1.4399252215 | 43.9925 % | 312.781399019 | 3.629480515 | 974 |
| 24 | 43x17 | 125.000 um | 4.0514540972 | 1.4417462061 | 44.1746 % | 312.780825091 | 3.629467196 | 1209 |
| 36 | 55x17 | 83.333 um | 4.0493407985 | 1.4409941698 | 44.0994 % | 312.780379041 | 3.629456844 | 1651 |

**Flat within noise, not converging.** The pair deltas are +0.0653 %, −0.1263 %, +0.0522 % — sign-alternating at the 1e-3 level, no monotone trend across a 3× range. The operand is flat to 0.13 % over that range.

**Every extrapolation lands in the same place.** Linear `R_inf` 4.0503776201 (44.14 % high), quadratic 4.0548481483 (44.30 %), Richardson on 12-18-24 (`p` = 0.954) 4.0540962691 (44.27 %), Richardson on 18-24-36 (`p` = −1.276, unidentifiable) 4.0442236458 (43.92 %), free power law `p` → 0.004 (no information in the exponents). All five land in 4.04-4.06: ~44 % high, ~4.4× outside the adopted band.

**The solves were healthy.** `corr_ey` 0.9208 → 0.9213 and `corr_ez_vv` 0.9353 → 0.9352 across the sweep, `modes_kept` = 1, `ok` = True, residual ~1e-16 on every row — the flatness is not a solve failing quietly.

**Verdict.** NO. Strip-band refinement neither reaches the bar nor moves the operand: 0.13 % of movement over 3×, against a miss of 4.408654619919989× the half-width. The 44.09 % disagreement is not strip-band discretisation, and further refinement of the strip cannot close it.

**A correction that matters.** The earlier `.scratch` three-mesh comparison (31x17 / 41x22 / 51x19 → `R_extracted` 4.049 / 3.771 / 3.566) looks O(h)-convergent and would extrapolate to `R_inf` of roughly 2.86-3.32, inside the band — but it changed the strip and the z band and the air band together. Isolate the strip and the apparent convergence is gone. Whatever residual sensitivity exists is in the z band, the air band, or the extraction definition, and is not something this sweep can see.

**The mesh is already graded.** The banked grading steps 9|12|9 across 0.9444 / 0.25 / 0.9444 mm and 8|4|4 up 0.2 / 0.5 / 1.0 mm (~3.8:1 in both directions), and `y` = 8.5 mm and `y` = 11.5 mm are node lines by construction (the PEC masks test `p[:,1] == 0.0` at 1e-12), so a uniform mesh cannot be built for this geometry at all. “Concentrate cells at the strip edges” therefore describes what the mesh already does, and “de-grade” is not an available move.

**What did not happen.** The bar is untouched: ±10 % relative on `Q`, `R_extracted` ∈ [2.52909192487721, 3.09111235262770], still FAIL at 4.408654619919989× the half-width. The §9.6 revisit is not invoked — this sweep establishes no mechanism, and it removes strip re-mesh from the list (§9.8 now measures the z band and the air band: the air band is the one that moves the operand, and it still does not reach the band; untested: the extraction definition). §9.4’s column/peak assertion remains unimplemented and §9.5’s “registered, not implemented” still stands: no `.py` compares `R_extracted` against `tol_rel`, and `m3c_gate_v2.md:630` still reads “Seven entries, no more.”

### 9.8 The first-axis air band and the z band, measured: the air band is the knob, and the band is still not attained

**Setup.** The knobs are `C1_Y_AIR_CELLS` = N, which sets both first-axis air bands and keeps them symmetric with the strip band held at 12, and `C1_Z_CELLS`, the second-axis triple, held at 8|4|4 unless stated — both in `tools/host/c1-audit/c1_audit.py`, both echoed into the run’s `mesh :` provenance line. The banked mesh is N = 9 (31x17 nodes). Every non-banked run carried `C1_ALLOW_REMESH=1`, which downgrades the banked-cache mesh-identity guard to a WARNING and leaves `bank_col = -1`, so REPRO overall: FAIL on those runs is by design and not a defect. `R_analytic = 2.8101021387524523` and the acceptance band is `[2.52909192487721, 3.09111235262770]` (§9.2).

**The strip band is flat — that is the contrast this section is measured against.** Strip cells 12 / 18 / 24 / 36 give `R_extracted` 4.0489791164 / 4.0463369445 / 4.0514540972 / 4.0493407985, pair deltas +0.0653 / −0.1263 / +0.0522 %, i.e. flat to 0.13 % over a 3x change in the strip cell size (§9.7).

**The air band is the real knob.** Six points, N = 6 / 9 / 12 / 15 / 18 / 22, with the grid, the first-axis air-band size in mm, the column, `R_extracted`, `Q`, the relative error, `beta`, `eps_eff`, `|corr_ey|`, the residual and the wall time:

| N | mesh | air band | column | `R_extracted` | `Q` | relative error | beta | eps_eff | `\|corr_ey\|` | residual | wall |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 25x17 | 1.416667 mm | 583 | 4.4382495593902 | 1.5793908 | +57.94 % | 314.732026 | 3.674891392 | 0.889292853 | 3.5e-16 | 16.6 s |
| 9 (banked) | 31x17 | 0.944444 mm | 738 | 4.0489791163983 | 1.4408655 | +44.09 % | 312.782764632 | 3.629512208 | 0.92077078 | — | — |
| 12 | 37x17 | 0.708333 mm | 809 | 3.7124820337398 | 1.3211200 | +32.11 % | 311.853118687 | 3.607969160 | 0.932607657 | 3.2e-16 | 49.6 s |
| 15 | 43x17 | 0.566667 mm | 845 | 3.5036000135 | 1.2467874 | +24.68 % | 311.309159199 | 3.595393513 | 0.93626159 | 2.9e-16 | 111.9 s |
| 18 | 49x17 | 0.472222 mm | 1018 | 3.4384391291194 | 1.2235993 | +22.36 % | 310.952759586 | 3.587165915 | 0.939677291 | 8.0e-16 | 122.8 s |
| 22 | 57x17 | 0.386364 mm | 1217 | 3.2761300897590 | 1.1658402 | +16.58 % | 310.635198670 | 3.579842860 | 0.941452306 | 8.2e-16 | 196.4 s |

The pairwise deltas are −8.7708 / −8.3107 / −5.6265 / −1.8598 / −4.7204 %, `corr_ez_vv` tracks 0.9131 → 0.9658 and `modes_kept` = 1 on every row. The sign printed on `corr_ey` and `corr_ez_vv` flips between runs (N = 6 and N = 15 print negative values); that is a sign convention on the candidate, not a health failure, so compare absolute values.

**Not asymptotic.** `R_extracted` falls monotonically in value, 4.0489791163983 → 3.2761300897590 = −18.6 %, but the decrements are not monotone: the N = 18 step collapses to −1.86 % and then falls again to −4.72 %. That one-off plateau means the sequence is contaminated at the 0.1 mm scale, and no extrapolation from it can be trusted.

**The extrapolants disagree by more than the miss.** Linear in h gives `R_inf` 2.8887847283 (+2.80 %, rms 5.03e-2) and quadratic in h gives 2.6071327418 (−7.22 %, rms 2.63e-2). Richardson triples: (6,9,12) with `p` = −0.5731 → 5.9264405 (+110.90 %), (9,12,15) with `p` = +0.8682 → 2.5264540 (−10.09 %), (12,15,18) with `p` = +4.6762 → 3.3900160 (+20.64 %), (15,18,22) with `p` = −4.2379 → 3.5595066 (+26.67 %). Fixed-`p` Richardson over all six points gives 1.8594054 (−33.83 %) at `p` = +0.4674, rms 3.02e-2, and the free power law converges to the same 1.85940534 at `p` = 0.4674, −33.83 %.

**The order is not identifiable.** A 9 x 11 x 6 multistart over (start, `R_inf`, `p`) found 193 degenerate minima, including a `p` ≈ −0.0002 ridge with `R_inf` ≈ 5000, so nothing in this sequence pins `p`. The total spread of the extrapolants, 1.86 to 5.93, is 144.7 % of the analytic reference — about five times the band half-width — so the extrapolants cannot place the band; the models disagree with each other by more than the miss they were invoked to explain.

**The z band goes the wrong way.** `C1_Z_CELLS` 8|4|4 → 12|6|8 (31x27, column 877) gives `R_extracted` 4.1029404210, `Q` 1.4600680753, +46.01 %, `beta` 312.952529607, `eps_eff` 3.633453162 — a move of +1.33 %, in the wrong direction. The next triple, 16|8|12 (31x37), is unreachable: 3264 free edges exceed the dense-pencil cap of 3000.

**The hard ceiling is exact.** Free edges = 48·nx − 44 with nx = 2N + 13. N = 24 gives 2884 free edges and runs; N = 25 gives 2980 free edges at nx = 63 / 1071 nodes and runs, with 20 slots of headroom; N = 26 gives 3076 and is REFUSED by `_MIXED_DENSE_MAX = 3000` in `c1_audit.py`, with the message “3264 free edges > _MIXED_DENSE_MAX 3000: the dense mixed pencil cannot run”. So the largest runnable mesh in this family is N = 25, h = 0.34 mm, and the three fits predict `R_extracted` = 3.273451 (linear) / 3.200400 (quadratic) / 3.189464 (power law) there — all of them still above the upper band edge 3.09111235262770. Raising the cap is deliberately not done: it is a different decision, about 1.4 GB or more of QZ work.

**The band test and the verdict.** Zero of the six measured points lies inside `[2.52909192487721, 3.09111235262770]`; the lowest measured `R_extracted`, 3.2761300897590 at N = 22, is still 6.0 % above the upper edge. `T4_amp` therefore still FAILS, the bar is untouched, and the verdict is that the band is **not** attainable by first-axis refinement of this mesh family, for two independent reasons: the sequence is not asymptotically clean, so no extrapolation is trustworthy, and the most optimistic fit at the hard mesh ceiling stays about 3.1 % high (the least optimistic says 1.86, so the models disagree more than the miss). §9.6’s revisit is still **not** invoked, because no mechanism has been established.

**A correction of the earlier framing.** The earlier meshes at 31x17 / 41x22 / 51x19 gave `R_extracted` 4.049 / 3.771 / 3.566; that trend was mostly the first-axis air band (41 nodes means 14 air cells, 51 nodes means 19), which this sweep confirms is the band that moves `R_extracted`. Refinement is therefore load-bearing — just not at the strip, and not enough to reach the band.

**Conditioning.** Over the same six points `beta` moves 314.732026 → 310.635198670 (1.3 %) and `eps_eff` moves 3.674891392 → 3.579842860 (2.6 %) while `R_extracted` moves 18.6 %, so `R_extracted` is the badly conditioned observable and the dispersion is not. Also worth recording: `R_extracted` is reduced on the **fixed** analytic lattices (200x77 and 201x76), not on FEM nodes, so the movement is field shape and not quadrature re-weighting.

**One known defect, recorded and not fixed.** The npz key `shape_pair_ok` stores only the shapes-match flag; the real verdict is the npz key `ok` (shapes AND both correlation thresholds AND finite). For N = 6, `shape_pair_ok` is True but `ok` is False (`corr_ey` 0.889293 is below the 0.89 bar), while the log’s VERDICT line prints `shape_pair_ok=False`. The script and the log disagree about what the flag means.

**Reproducibility.** Every point above is one run of `tools/host/c1-audit/c1_audit.py` with `C1_Y_AIR_CELLS` / `C1_Z_CELLS` set and `C1_ALLOW_REMESH=1`, writing an npz under `out/mesh_study/` (`yair06`, `yair12`, `yair18`, `yair22`, `z12_6_8`), none of which is committed. The banked captures at `tools/host/c1-audit/out/` were verified unchanged after every run: `c1_spectrum.npz` sha256 `05387390cf2977364c2e6f62a1c694149fc13754d054c9c51bbccbabcf9568d4` and `pecbox_spectrum.npz` sha256 `92d283155a5e2fe5607e5867f8ebab2d7861c682e60274a8667f5dcd80340f18`.

## 10. The extraction verdict: the extraction is correct, the sensitivity is physical

The question this section answers is narrow and was raised by §9.2 and §9.8 themselves: are the 44.09 % of §9.2 and the monotone fall of §9.8 an artefact of *how* `R_extracted` is measured, or a real property of the discretisation? The answer is that the measurement is correct — no weight, area element, lattice or resampling defect stands behind it — and the sensitivity is physical, living in the `e_y` denominator, which is still gaining edge energy as the mesh refines. The basis is a fresh audit of the reduction path (226.7 s / 222 tool calls, high confidence), reading the banked arrays and the emitting code rather than re-running anything. **No number in §9.2 changed, and §9.6's revisit clause was not invoked**: this section explains a movement, it does not re-register a mechanism, and it moves neither the bar nor the verdict.

### 10.1 Where R is computed — one site, four lines

`R_extracted` is defined at exactly one place in the codebase: `c1_audit.py:766`, as `R_extracted = float(R_by_col[banked_idx])` on the per-column energies appended at `c1_audit.py:705` and reduced at `c1_audit.py:746-747`, carried into the single `np.savez(` call at `c1_audit.py:816`. There is no library-side definition of the ratio anywhere; `pecbox_variant.py:702,712` mention it only inside comments. Everything that follows is therefore about those two arrays and nothing else — a defect would have to be in how `e_y` and `e_z_vv` are built or reduced, because there is nowhere else for one to live.

### 10.2 The two operands and their lattices

| operand | source line | array shape | lattice | where it lands |
|---|---|---|---|---|
| `e_y` | `c1_audit.py:679-680` | (200, 77) | y cell-centres × z nodes | the dielectric interface z = 1.6 mm |
| `e_z_vv` | `c1_audit.py:686-687` | (201, 76) | y nodes × z cell-centres | the strip edges y = 8.5 / 11.5 mm |

`e_y` is built at `c1_audit.py:679-680` as `E_t = MODE.e_at(_ey_pts).reshape(NYN - 1, NZN, 2)` then `e_y = E_t[:, :, 0] * CELL`; `e_z_vv` at `c1_audit.py:686-687`. The two lattices are deliberately staggered, and that is correct FEM practice rather than an accident: the in-plane component is wanted where its normal direction is resolvable, the vertical component where the singular edge lives. The interpolant is `Mode2D.e_at` at `emfit/mode2d.py:742-781`, a piecewise-linear Whitney 1-form evaluation `e_t(p) = Σ_s w_s [λ_a ∇λ_b − λ_b ∇λ_a]` — no bilinear interpolation, no `griddata`, no FFT, no resampling anywhere in the path, so the sampled values are the field and not a filtered version of it. The analytic counterparts are guarded for shape at `c1_audit.py:598-602`, which is what makes the two operands comparable at all rather than silently broadcast.

### 10.3 No weight or area element is missing

The ratio is plain node sums of squares: no quadrature weights, no trapezoid factors, no background subtraction, so no cancellation is possible, and a dropped weight could only appear as a common scale factor — which cancels in a ratio. Quantified rather than asserted: switching *both* operands to a trapezoid-weighted sum moves the analytic ratio by **+0.0223 %** and the extracted ratio by **+0.0175 %**, i.e. the whole weighting question is worth two parts in ten thousand. **What did not happen:** no mass-matrix weighting was applied anywhere in the reduction, and none was needed for a like-for-like comparison, because both operands are reduced by the same rule on the same kind of lattice.

### 10.4 Bit-exact reproduction

The numbers are reproducible from the stored npz payloads with relative difference **0.00e+00** on all six mesh-study captures and on the pecbox capture, via `tools/host/c1-audit/mode_plot.py`'s `reconstruct_run` with `mp.C1_OUT` patched; the N = 9 value reproduces as `4.0489791163983`. No partial sums are quoted here: the intermediate accumulations in the working notes were garbled and are not authoritative, so only quantities that reconstruct bit-exactly are used as evidence in this section.

### 10.5 Like-for-like was tested, not assumed

| variant | `R_analytic` | `R_extracted` | d(analytic) | d(extracted) |
|---|---|---|---|---|
| as written | 2.8101021387525 | 4.0489791163983 | — | — |
| boundary planes dropped | 2.8113577527841 | 4.0503951543184 | +0.0447 % | +0.0350 % |
| interior window y ∈ [1, 19] mm, z ∈ [0.5, 7.0] mm | 2.2382725482956 | 3.0730766300207 | −20.35 % | −24.10 % |
| trapezoid weighting | 2.8107297770527 | 4.0496869679447 | +0.0223 % | +0.0175 % |
| de-staggered onto a common 200×76 cell-centre grid | 2.8431489615431 | 4.0611143983338 | +1.176 % | +0.2997 % |

The worst-case lattice/domain asymmetry is **1.18 %** on the analytic operand and **0.30 %** on the extracted one, and the two operands move *together* under every variant — including the interior window, where they move by −20 % and −24 % in the same direction — so the 44 % gap cannot be bookkeeping. The de-staggered row is the decisive one: forcing both operands onto one lattice, which is the strongest available test of the staggering noted in §10.2, costs 1.18 % on the denominator and 0.30 % on the numerator.

### 10.6 Why the ratio falls with refinement — the denominator is still gaining edge energy

**75.30 %** of the analytic `e_z` energy sits in **14.43 %** of its samples, and dropping edge columns moves the analytic ratio the *wrong* way (k = 1: analytic `2.9646`, extracted `3.8558`), i.e. the singular edge structure defines the mode and cannot be trimmed away. The `e_y` denominator is the operand still converging: its share of energy within 1.5 cells of the strip edge climbs monotonically **7.23 % → 15.79 %** across N = 6 … 22, toward the analytic **22.67 %**, while `e_z_vv`'s edge share is flat (12.39 % → 14.23 %) and its substrate share stays pinned at 87–89 % against an analytic 78.65 %. A ratio whose denominator keeps gaining edge energy *must* fall — and it does, from `4.4382495593902` to `3.2761300897590` — while `beta`, which is a global weighted quantity, moves only 1.3 % (`314.73` → `310.64`).

**A correction, and an explicit limit.** Convergence to `2.810102138752` is plausible but **unproven**. The successive decrements (−0.389, −0.337, −0.209, −0.066, −0.162) are monotone in value but not extrapolable — the −0.066 plateau is the same contamination §9.8 records — and the data cannot distinguish a limit of 2.8101 from one near 3.0. "The denominator is converging toward the analytic edge share" is a mechanism; "it converges to the analytic ratio inside the bar" is not a result this evidence supports.

### 10.7 The three questions that were asked

1. **Integration domain.** The full modelled cross-section, each operand on its native lattice; the de-staggered test of §10.5 bounds the resulting asymmetry at 1.18 %, and the interior-window test bounds domain-truncation sensitivity at −20 % only when the domain is cut to a quarter of the geometry, which is not what the banked reduction does.
2. **Weight / area element.** None missing; the trapezoid variant is worth 0.02 %, so the ratio is not sensitive to that choice in either direction.
3. **Is `e_z_vv` pointwise-sampled at the interface rather than averaged?** Yes — and that is right for a Whitney 1-form, whose tangential component is continuous across a dielectric interface, so pointwise sampling of the tangential component is the correct choice and averaging would be wrong. This was the one candidate defect that, if real, would have invalidated the ratio; it is not real.

### 10.8 What this does and does not change about the bar

§9.2's `±10 %` band, the band endpoints `[2.52909192487721, 3.09111235262770]`, `Q = 1.440865461991999` and the 44.086546199199894 % miss are unchanged by this section; §9.6's revisit clause is **not** invoked, because a diagnosis of *why* `R` moves is not a pre-registered threshold mechanism; §9.4 remains unimplemented and §9.5's "registered, not implemented" wording still stands, with `m3c_gate_v2.md:630` still reading "Seven entries, no more."

With the extraction exonerated and the residual sensitivity identified as a genuine finer-mesh effect in the `e_y` denominator, the binding constraint is the **solver ceiling** at N = 25 (§9.8) — 2884 to 2980 free edges against `_MIXED_DENSE_MAX = 3000` — not the measurement. `docs/design/sparse_eigenmode.md` addresses that ceiling as a **design pass, unanchored until implemented and gated**, and its numbers are quoted here strictly as measurements of the solver, never as results about `R`: at the 201×77 mesh, `splu` fill-in 8,352,700 nonzeros (0.00228 of the dense `n²`, about 100.2 MB), 0.38 s factorisation, 12.82 ms per shift-invert apply, against 16.7 GB and roughly 41 days for the dense QZ path.

### 10.9 Six latent script-versus-log defects (recorded, not fixed)

| # | defect | evidence | impact |
|---|---|---|---|
| 1 | `shape_pair_ok` carries two different meanings | header at `c1_audit.py:778-780` defines it as `\|corr_ey\| >= 0.89 and \|corr_ez_vv\| >= 0.91 and shapes match`; the printed column at `:809` (stdout mirror `:905`) writes the real `ok_arr` from `:724-726`; the npz key at `:841` stores only shape equality. `out/mesh_study/yair06/c1_spectrum.npz` has `ok=[False]` with `shape_pair_ok=[True]`; `out/pecbox_spectrum.npz` has `ok=[True,False]` with `shape_pair_ok=[True,True]` | the npz key is the unsound one — same defect §9.8 records as "one known defect", reached from the other side |
| 2 | npz key `corr_ez` at `:830` aliases `corr_ez_superseded_longitudinal` | the mis-paired ≈ +0.12 metric; `mode_plot.py:278-291` compares the alias against banked longitudinal anchors | readers must use `corr_ez_vv`; the alias silently answers a different question |
| 3 | `out/pecbox_spectrum.npz` stores `bank_col=738` (a PMC column) | its own `j=[699,704]` | the PEC capture names a column it does not contain |
| 4 | `pecbox_variant.py:706` cites `c1_audit.py:662` as the npz site | the npz call is at `:816`, `R` at `:766` | provenance citation off by 154 lines; follow-up audits land on the wrong statement |
| 5 | stored PEC `R_extracted = 70.635018555128326` is the *last scanned* failing-witness column, 704 (`corr_ey = -0.426418989`, `corr_ez_vv = -0.083134346`) | the identified column 699's `R = 4.163656524825077` is on record in `c1_audit.py` (`:203-210`, `:885`, `:999`) but still in no artefact — the banked npz predates the fix and is deliberately not overwritten (`:210-213`) | the PEC leg's quotable `R` is **unbanked**; a PEC scoring run must read it from `R_by_col` (`:862`) or `R_extracted` (`:888`) after a re-run, not from the banked scalar |
| 6 | `bank_col = -1` in all six mesh-study npz files | unset, not wrong | none — recorded for completeness |

All six are latent: none is fixed by this section, and none affects a banked verdict. Defect 5 is the one with a live consequence — the PMC leg is the scored leg precisely because its `R` is banked on the column it was computed on.

### 10.10 Open items

- `R`'s limit is not established (§10.6): the sequence supports a mechanism, not a limit value, and 2.8101 cannot be distinguished from a limit near 3.0 on this data.
- `T4_amp` is still unimplemented as a gate clause, and `docs/design/m3c_gate_v2.md:630` still reads "Seven entries, no more."
- The six defects of §10.9 are recorded but not fixed; defect 5 leaves the PEC leg's `R` unbanked.
- Whether the global `argmax(beta**2)` at `emfit/mode2d.py:1167` selects the fundamental at all is open — raised in `docs/design/sparse_eigenmode.md` §7, not measured.

## 11. Citation repair: the t4 witness chain

Every `c1_audit.py` line number in §9 and §10 above was verified against the
script as it stands today (1015 lines) and repaired where stale. Lines 1–51
(header, §1–§8) were out of scope by instruction on the first pass and were
left stale, so a reader is not misled into trusting them; their stale cites
are recorded at the end of this section beside the numbers that replaced
them. They have since been repaired too — by symbol, one site at a time,
because no single offset fits (§11.4). The head therefore moved, and the
earlier claim that it had not is withdrawn: `head -51 | sha256sum` was
`4abbadd18c77018758db6a74ea4393ce761fb916aab62db724fa524307a80f54` (8,124 bytes) — and had in fact already drifted one witness further before this pass, to `323b9125…`, at the same 8,124 bytes — and is now
`b6baa72679f0226549cc3f28746c60bb3134e6eff7b240d8d3f9daffdf16db82` (9,008 bytes), computed with the
same method on both sides. Likewise the "line count unchanged (256 lines)" that
stood here described the 256-line file it touched; §12 has since grown the
file and this pass adds a paragraph to §2 and one to §12.6, so the count
moves too: 533 lines before this pass, 547 after.

### 11.1 Edits made

| line | § | symbol | old cite | new cite |
|---|---|---|---|---|
| 188 | 10.1 | `R_extracted` assignment | `:738` | `:766` |
| 188 | 10.1 | `np.savez(` call | `:703` | `:816` |
| 194 | 10.2 | `e_y` build | `:506-520` | `:679-680` |
| 195 | 10.2 | `e_z_vv` build | `:607-615` | `:686-687` |
| 197 | 10.2 | `e_y` build (prose) | `:506-520` | `:679-680` |
| 197 | 10.2 | `e_z_vv` build (prose) | `:607-615` | `:686-687` |
| 197 | 10.2 | analytic shape guard | `:523-535` | `:598-602` |
| 241 | 10.9 #1 | printed `shape_pair_ok` criteria header | `:670` | `:778-780` |
| 241 | 10.9 #1 | `ok_arr` printed column | `:696` | `:809` (stdout mirror `:905`, added) |
| 241 | 10.9 #1 | `ok_arr` definition | `:651-653` | `:724-726` |
| 241 | 10.9 #1 | npz key `shape_pair_ok` | `:720` | `:841` |
| 242 | 10.9 #2 | npz key `corr_ez` alias | `:717` | `:830` |
| 244 | 10.9 #4 | npz call / `R` (in the impact cell) | `:703` / `:738` | `:816` / `:766` |
| 244 | 10.9 #4 | size of the provenance error | 41 lines | 154 lines |

### 11.2 The offsets are not uniform, which is why no single `+N` repairs this

| symbol | old | new | offset |
|---|---|---|---|
| `e_y` build | 506-520 | 679-680 | +173 (and 15 lines → 2) |
| `e_z_vv` build | 607-615 | 686-687 | +79 (and 9 lines → 2) |
| `ok_arr` definition | 651-653 | 724-726 | +73 |
| header string | 670 | 778-780 | +108 |
| printed `ok_arr` column | 696 | 809 | +113 |
| `np.savez(` call | 703 | 816 | +113 |
| npz `corr_ez` alias | 717 | 830 | +113 |
| npz `shape_pair_ok` | 720 | 841 | +121 |
| `R_extracted` assignment | 738 | 766 | **+28** |

The last row is the interesting one. `R_extracted` has not drifted *up* with
the rest of the script: it has drifted up by only 28 lines, because the
reduction itself moved. It used to be written inline inside the `np.savez(`
call as `R_extracted=float(np.sum(e_z_vv ** 2) / np.sum(e_y ** 2))`. It no
longer lives there. The script now accumulates per-column energies inside the
column loop (`energies.append((float(np.sum(e_y ** 2)), float(np.sum(e_z_vv ** 2))))`,
`:705`), reduces them after the loop (`R_by_col = np.array([ez / ey for (ey, ez) in energies])`,
`:746-747`), selects the banked column (`R_extracted = float(R_by_col[banked_idx])`,
`:766`), and only then passes the scalar into `np.savez(` at `:816` as
`R_extracted=R_extracted,`. The arithmetic is identical — the ratio of a
column's summed squares — but the *region* between the old and new site
shrank by 85 lines while everything after it grew, so the sum of the two
movements is the +28. A blanket offset applied to this document would have
landed on the loop body, not on the assignment.

§10.1's quoted source has been updated to the current three stages for the
same reason: the old quotation of the `np.savez` argument is now text that
does not exist anywhere in the script, and leaving it would have been a
worse defect than the stale line number it was attached to.

### 11.3 Verified as still correct (no edit)

- `emfit/mode2d.py:742-781` — `Mode2D.e_at`, the Whitney 1-form evaluator (§10.2).
- `emfit/mode2d.py:1167` — the global `argmax(beta**2)` mode selection (§10.10).
- `emfit/studies.py:3242-3246` — the `freqs=np.empty(0)` sentinel (§10.4).
- `decisions.md:7956` — "…has not been computed." (§10.6, §10.10).
- `docs/design/m3c_gate_v2.md:630` — "Seven entries, no more." (§10.10 and §2).
- `pecbox_variant.py:706` — the comment that records the last-column-wins defect.

### 11.4 What was left stale, and what was repaired later

- **§1–§8 (lines 1–51): left stale first, then repaired.** When §11 was written
  these lines were out of scope, and they cited `c1_audit.py:430-433`,
  `:437-441`, `:632` (§1), `:513-514`, `:520-521`, `:528-534`, `:609-635` (§2) and
  `:528-534` again in §2's prose. They have since been repaired at those same
  sites, by symbol, to `:593-594`, `:600-602`, `:871`, `:679-680`, `:686-687`,
  `:705`, `:746-747`, `:816` and `:694-695`. No offset would have found them:
  the offsets run from `+163` (`:430-433` → `:593-594`) to `+239` (`:632` → `:871`),
  and the reduction `:528-534` maps to no single line at all, because the
  correlation calls and the energy sums now live apart (`:694-695`, `:705`).
  The record that these cites were once stale is kept here rather than dropped.
- **`pecbox_variant.py:706`'s own embedded cite** (`c1_audit.py:662`). This
  is a defect *in the script*, recorded as §10.9 #4 and explicitly not fixed
  there; repairing the prose that reports it would erase the evidence.
- **`decisions.md:7948`'s embedded cite** (`c1_audit.py:510-511` for the
  `e_z_vv` read). §8 of this document already flags it as a Miscite and
  supplies the correct construction; today that construction is `:686-687`.
  The decision log is append-only and is not edited from here.

### 11.5 Standing caution

The offsets above are a snapshot of a 1015-line script that is still being
edited. Line numbers are volatile; symbols are durable. `R_extracted`,
`e_y`, `e_z_vv`, `np.savez(`, `shape_pair_ok`, `corr_ez`, `R_by_col` are what
should be grepped when this document is next audited — the numbers in §9–§11
are a convenience, not the claim.

## 12. Mesh refinement: the first two rungs

### 12.1 What was measured, and what it is not

A committed harness at `tools/host/sparse-probe/` refines the C1 mesh and re-extracts
`R_extracted` at each rung, starting from the banked mesh. It drives the **existing
dense-QZ pipeline** — the same `c1_audit.py` code path that produced the banked
capture, only larger.

It is **not** a sparse solver, because the sparse solver does not exist. `emfit`'s
iterative path is a stub that raises `NotImplementedError` (`emfit/mode2d.py:1095-1099`),
and the mixed solve refuses any mesh above `_MIXED_DENSE_MAX = 3000` free edges
(`emfit/mode2d.py:151`), which `c1_audit.py:463-465` turns into a `SystemExit`. Rungs
above that cap are reachable only through `C1_ALLOW_DENSE_ABOVE_MAX=1`, which the
driver sets for exactly those rungs. The sparse path is a design note,
`docs/design/sparse_eigenmode.md`; nothing in this ladder implements it.

The consequence of staying dense is the reason the ladder is interpretable at all:
the mode-selection path, the eligibility filter (`|corr_e_y| >= 0.89 and
|corr_ez_vv| >= 0.91 and shapes match`), the column-selection rule and the extraction
are byte-identical to the registered run at every rung, so `R_extracted` is directly
comparable to the banked value with no re-registration and no changed rule. **`h` is
the only changing variable.**

Rung 0 is the control: same mesh as the banked capture (`31 x 17` nodes,
`free_e = 1444`), and it reproduces the banked `R` to 7.9e-13 relative. It is a gate,
not a sixth data point.

One reading rule, because it will otherwise be misread: the QZ column index is a
diagnostic and never a mode identifier. On the identical rung-0 mesh the solver
selects column 732 while the banked cache holds 738, for the same mode, with `R`
agreeing to 8e-13. The rungs are compared by `free_e`, `R_extracted` and `beta_sq`.

### 12.2 The data

`R_analytic = 2.8101021387524523` (§1, unchanged). `Q = R_extracted / R_analytic`;
the amplitude error is `|Q - 1|`.

| rung | strip / y_air / z | free_e | `R_extracted` | `Q` | error | wall |
|---|---|---|---|---|---|---|
| 0 (control) | 12 / 9 / 8\|4\|4 | 1444 | 4.0489791163982565 | 1.440865461991999 | 44.086546199199894 % | 20.1 s |
| 1 | 16 / 12 / 10\|5\|5 | 2404 | 3.780331990015745 | 1.345264977341367 | 34.5264977341367 % | 108.7 s |

The rung-0 entry is the registered `R_extracted` (PMC leg); the fresh control runs
print `4.0489791163950715`, which is that value to 7.9e-13 relative. Using either
moves no digit quoted anywhere in this section.

**Rung 1's guard evidence**, so that it can be seen to have passed the same shape
test as the control rather than being a lucky pick: `n_eligible = 1`, the single
eligible column 1224, `|corr_e_y| = 0.938008867` (threshold 0.89),
`|corr_ez_vv| = 0.948121954` (threshold 0.91), `ok = True`, `beta_sq = 97328.3081094`
(the selected mode's eigenvalue, of order `eps_r k0^2 = 1.185e5`), and
`free_e = 2404 = 2460 edges - 56 PEC edges`, recomputed from `strip = 16`,
`y_air = 12`, `z = 10,5,5` and asserted against the built mesh. The control's
`corr_e_y` was 0.92077078481114194 (§9.7), so the gating correlations do not merely
re-pass at rung 1 — they improve.

Rung 1's driver reports `repro: FAIL` by design: a re-meshed run has no banked column
to reproduce, so the check has nothing to compare and is expected to fail. The control
is rung 0, and rung 0 passed. The failure is not a fault and is not evidence.

### 12.3 The implied order, labelled as an indication

In two dimensions a uniform refinement that quadruples the free-edge count halves the
cell size, so `h ∝ free_e^(-1/2)`:

    h1/h0 = sqrt(1444 / 2404) = 0.775026165625604

With `e ≡ |Q - 1|`, `e0 = 0.440865461991999` and `e1 = 0.345264977341367`:

    e1/e0 = 0.7831527010107066
    p     = ln(0.7831527010107066) / ln(0.775026165625604) = 0.9590717710780169

i.e. `p ≈ 0.96`, consistent with first order (`error ∝ h`). Anchoring `e ∝ h^p` at
rung 0 and predicting rung 1:

    p = 1 :  Q1 = 1 + e0 * (h1/h0)^1 = 1.3416822685644194   (observed 1.345264977341367, +0.27 %)
    p = 2 :  Q1 = 1 + e0 * (h1/h0)^2 = 1.2648126984677397   (observed 6.4 % above it)

So `p = 1` is close and `p = 2` is already disfavoured by this one extra point.

**Two points indicate an order; they do not establish one.** With two points and two
free parameters the log-log line passes through both exactly: `p` here is a one-degree-
of-freedom statistic with no residual, so it carries no goodness of fit, no error bar
and no outlier test. It is a consistency statement — the movement is the size first
order predicts — and rungs 2 and 3 are what decide.

### 12.4 What this does and does not overturn

It does not overturn §10. Section 10 audited *how* `R_extracted` is computed — which
arrays, which lattices, which reduction, which artefact — and found the path correctly
implemented. Nothing here reopens that: the ladder runs the same path and obtains the
banked number at the banked mesh. §10 was never a claim that `h` is irrelevant; it was
a claim that the measurement is not distorted by the way it is taken.

What is now under test is a different and further claim: that the 44 % gap is
dominated by physics rather than by discretisation. On this data that claim is not
supported in the strong form. The first refinement step moves `R_extracted` by
`0.26864712638251165` — 6.634934848008922 % of its value, 21.684729898929323 % of the
gap to `R_analytic` — and the amplitude error falls by a fifth, from 44.09 % to
34.53 %. The mesh is demonstrably a live lever on the operand, not a settled detail.
Equally, one step that closes a fifth of the gap is not a convergence: §9.8's monotone
fall and this step are the same movement seen twice, and neither establishes a limit.

### 12.5 The consequence

The band is `|Q - 1| <= 0.10`, i.e. `R_extracted ∈ [2.5290919248772, 3.0911123526277]`.
From rung 1 the error must fall by

    e1 / 0.10 = 3.4526497734136700x

With `p = 1`, `h` must fall by that same factor, so `free_e` must rise by its square:

    h_target/h1 = 3.4526497734136700
    free_e = 2404 * 3.4526497734136700^2 = 2404 * 11.9207946525 = 28657.60  ≈ 2.9e4

Carrying the fitted `p = 0.9590717710780169` instead of 1:

    h_target/h1 = 3.4526497734136700^(1/0.9590717710780169) = 3.6406
    free_e = 2404 * 3.6406^2 = 31854.5  ≈ 3.2e4

Both are quoted because the order of magnitude is the claim, not the digit: the
registered band needs three to four times finer `h`, `free_e` of order `3e4`.

That is out of dense reach on this machine. Under the driver's documented cost model
(`peak RAM ≈ 5.5 * 8 * free_e^2` bytes, `wall ≈ 45 s * (free_e/1444)^3`), `free_e`
≈ 2.9e4 projects to ≈ 3.6e10 bytes (33.6 GiB) and ≈ 3.5e5 s (≈ 98 h); the fitted
target of 3.2e4 projects to ≈ 4.5e10 bytes (41.6 GiB) and ≈ 134 h. For scale, rung 4 —
`free_e = 9604`, the largest rung anyone has costed — already projects to 3.78 GB peak
and 13239 s (3.68 h). The band therefore sits nine to eleven times rung 4's memory and
twenty-six to thirty-seven times its wall clock away, on a path that scales as
`free_e^2` in memory and `free_e^3` in time.

**That is the concrete case for the sparse design.** It is not a performance
optimisation of an existing capability, and it is not a nicer way to reach a mesh we
could already afford: at first order the dense path cannot reach the registered band
at all. The sparse path is the only route to it. That reframes the sparse work from an
efficiency project to a precondition for the gate.

One caveat on the two numbers above: the cost model is documented and deliberately
generous, not measured (`README.md`, "Cost model"), and it is anchored at 45 s per
rung-0-equivalent, which is ~2x pessimistic against rung 0's own log. The *scaling*
argument is unaffected — it is the exponent, not the constant, that puts `3e4` out of
reach — but the absolute GiB and hours are soft by a factor of about two in the
optimistic direction.

### 12.6 What is still open

Rungs 2, 3 and 4 (`free_e` 3604, 5044, 9604) were **not run** when §12.2 was written. The command is

    tools/host/sparse-probe/high_res_run.sh --include-rung4

and the driver projects rungs 0-4 at 16110 s total (4.47 h), rung 4 alone at 13239 s
(3.68 h). That projection is not firm: it is the driver's own model, and the one rung
where a projection can be checked against a measurement ran long — rung 1 was
estimated at 208 s and took 108.7 s, i.e. the estimate was 1.91x pessimistic (rung 0:
45 s projected, 20.1 s measured, 2.24x). The driver replaces its 45 s base with rung
0's measured clock as soon as rung 0 finishes, so the revised estimates for rungs 2-4
are shorter again. Treat 4.47 h as an upper bound of order two times too large, not as
a scheduled duration.

**Status of the ladder as this is written.** The full dense ladder is now running on the host, rungs 0–4, in one **anchored** pass driven by `tools/host/sparse-probe/high_res_run.sh --include-rung4`. Rungs 0–3 have written their captures: `out/rung0_s12_a9_z8-4-4/` (22:38), `out/rung1_s16_a12_z10-5-5/` (22:40), `out/rung2_s20_a15_z12-6-6/` (22:46), `out/rung3_s24_a18_z14-7-7/` (23:08); rung 4's directory was created at 23:08 and holds only its `env.json` and `run.log`. The earlier pass's rung directories were parked under `out/prev/` rather than deleted, so both passes stay inspectable. That earlier pass is the one that left `out/summary_HIGHRES.txt` behind, and its own step 1 reads "rung 0 did not run: the ladder is unanchored and nothing below applies" — yet it went on to print `T4_amp: FAIL` from the rung-1 operand. A pass in which rung 0 never anchored the ladder is a pass whose lower rungs do not apply, so that verdict was not a verdict. Commit `a72530f` fixed the harness so the failure cannot recur: a run whose rungs do not start at rung 0 now refuses outright (`tools/host/sparse-probe/high_res_run.py:966`, "the ladder would be UNANCHORED"), and a pass that reaches the verdict step without a rung-0 anchor writes `T4_amp: NOT EVALUATED` instead of a verdict (`:1126-1127`, emitted at `:1139`). The rung 2, 3 and 4 numbers are **not** tabulated here — §12.2 stops at rung 1 by construction — and they will be recorded as a new section when the pass completes.

The decision rule was registered before any rung of this ladder ran, in
`tools/host/sparse-probe/evidence/ladder/summary_HIGHRES.txt`, and is quoted verbatim:

> (d1) |R_extracted - R_analytic| falls monotonically and the 1/n_free extrapolant lands
>      inside the band  ->  the discrepancy is discretisation, and the bar can be met by
>      a run at the fitted resolution;
> (d2) it is flat or non-monotone, or the extrapolant stays above 3.09111235262770
>      ->  the mesh is NOT the mechanism, and the ladder has eliminated it.

In plain terms: if `R` tends to `2.8101` as `h -> 0`, the gap was discretisation; if
`R` plateaus at `~4.049`, the gap is genuine physics and the mesh is not the mechanism.

The plateau branch is **not** what the current data show: rung 1 sits 0.2686 below the
control, which is movement, not a plateau. But one refinement step is not enough to say
what the data do show either — `d1` requires monotonicity *and* an extrapolant that
lands inside the band, and with two points there is no defensible extrapolant (§12.3:
no residual, no error bar). The honest statement is that the sequence has started to
move in the `d1` direction and that the two branches remain live until rungs 2 and 3
are measured.

## 13. The ladder completed: five rungs, one sparse cross-check, and the branch it returns

Section 12 was written with two rungs measured and three outstanding. All five have now been run
in one **anchored** pass (`tools/host/sparse-probe/high_res_run.sh --include-rung4`), `free_e`
1444 to 9604, 11591.3 s of solver time in total (3.22 h; the driver's own wall clocks sum to
11593.8 s), and the largest mesh has additionally been re-solved by the sparse path as a
cross-check (13.6). What the completed ladder returns is the plateau branch of the decision rule
that was already in place before it ran, `(d2)`, and the `T4_amp` verdict is unchanged: **FAIL**,
`|Q - 1| = 0.27234263263559066` against an allowance of `0.10`.

Two boundaries, stated first because both are easy to overread. This is not a convergence study:
five points on an irregular ladder whose increments change sign do not establish an order, and
every order quoted below is labelled a diagnostic. And it is not a sparse solver result: Route C
is one solve at one mesh, scored against the dense answer at that same mesh. It says the sparse
path is correct at the largest rung. It says nothing about convergence.

### 13.1 What was run, and what it is not

Five rungs of the **existing dense-QZ pipeline** - `tools/host/c1-audit/c1_audit.py`, the code
path of 12.1, unmodified - driven in one pass by
`tools/host/sparse-probe/high_res_run.sh --include-rung4`. The mode-selection path, the
eligibility filter (`|corr_e_y| >= 0.89`, `|corr_ez_vv| >= 0.91`, shapes match), the
column-selection rule and the extraction are byte-identical at every rung, so `R_extracted` is
directly comparable to the banked value with no re-registration and no changed rule. Within this
family, `h` is still the only changing variable.

Rung 0 is unchanged as the control: the fresh run reads `4.0489791163950715` against the banked
`4.0489791163982565`, a relative difference of `7.866199655477237e-13` against a gate of `1e-6`,
with `n_eligible = 1` and both reproduction checks passing (`e_y` `1.956e-13`, `e_z` `2.755e-11`,
`REPRO overall: PASS`). The ladder is scorable.

Rungs 1 to 4 each carry `C1_ALLOW_REMESH=1`, and rungs 2 to 4 also carry
`C1_ALLOW_DENSE_ABOVE_MAX=1` because their `free_e` (3604, 5044, 9604) exceeds
`_MIXED_DENSE_MAX = 3000`. Each of those rungs therefore rebuilds a mesh that is not the banked
one and each therefore prints `repro: FAIL`. That is a statement about mesh identity, not about
numerical validity; it is documented in 13.2 so it cannot be mistaken for a fault.

Cost, **MEASURED**. Rung 4 alone took `9784.3` s, which is 84.41 % of the ladder's 11591.3 s. One
dense matrix at `free_e = 9604` is

    9604^2 * 8 B = 737894528 B

which the driver's own banner prints as `0.687 GB` - that figure is **GiB**; in decimal it is
`0.7379 GB`, and the rung-4 `c1_spectrum.npz` on disk is `738560423` B. The QZ work arrays are
`~5.5 x` that, printed by the banner as `3.78 GB peak`, i.e. `3.7797 GiB` = `4.0584 GB`.

The column index is a diagnostic, as in 12.1, and rung 4 selected column 5133. Nothing below is
compared by column index.

**One correction to 12.2, flagged here because 12.2 may not be edited.** The two wall clocks in
12.2's table (`20.1 s`, `108.7 s`) come from the earlier, unanchored pass whose directories are
now parked under `out/prev/`. The anchored pass behind `summary_HIGHRES.txt` reports `19.2 s` and
`105.8 s` as the audit self-report (`19.7 s` and `106.2 s` of driver wall clock). The `R`, `Q` and
error entries are unaffected - the two passes agree on those to every digit 12.2 quotes - but
those two wall clocks are superseded and are not used in this section.

One further reading note on durations. Each rung has two timings: the driver's wall clock and the
audit's own self-report. At rung 4 they are `9784.9` s and `9784.3` s. Every duration quoted in
13 is the self-report, because that is the number the log line records
(`run.log:71`, `DONE ... elapsed=9784.3s`).

### 13.2 The data

`R_analytic = 2.8101021387524523` (section 1, unchanged). `Q = R_extracted / R_analytic`; the error
is `100*(Q - 1)`; the excess column is `100*(R/3.09111235262770 - 1)`, i.e. how far above the
band's upper edge each rung sits. Every rung of the ladder is above it.

| rung | strip / y_air / z | free_e | `R_extracted` | `Q` | error vs `R_analytic` | excess over band hi | REPRO | wall |
|---|---|---|---|---|---|---|---|---|
| 0 (control) | 12 / 9 / 8\|4\|4 | 1444 | 4.0489791163982565 | 1.440865461991999 | 44.086546199199894 % | 30.9877692719998 % | PASS | 19.2 s |
| 1 | 16 / 12 / 10\|5\|5 | 2404 | 3.7803319900157453 | 1.3452649773413672 | 34.52649773413672 % | 22.296816121942385 % | FAIL (expected) | 105.8 s |
| 2 | 20 / 15 / 12\|6\|6 | 3604 | 3.5673083405263886 | 1.2694586048427758 | 26.945860484277585 % | 15.405327712979533 % | FAIL (expected) | 404.8 s |
| 3 | 24 / 18 / 14\|7\|7 | 5044 | 3.6127170292894397 | 1.2856176932036034 | 28.56176932036034 % | 16.874335745782034 % | FAIL (expected) | 1277.2 s |
| 4 | 36 / 22 / 20\|10\|10 | 9604 | 3.575412753195199 | 1.2723426326355907 | 27.234263263559065 % | 15.667512057780897 % | FAIL (expected) | 9784.3 s |

*MEASURED - each cell read from that rung's own `run.log` and `c1_table.txt`.*

The selected mode at each rung, which is what the rungs are actually compared by:

| rung | free_e | `beta_sq` | `eps_eff` |
|---|---|---|---|
| 0 | 1444 | 97833.0578510 | 3.629512208 |
| 1 | 2404 | 97328.3081094 | 3.610786479 |
| 2 | 3604 | 97049.1256062 | 3.600429077 |
| 3 | 5044 | 96873.8886804 | 3.593927956 |
| 4 | 9604 | 96752.5197006 | 3.589425284 |

*MEASURED - the selected column's own record, read from the same `c1_table.txt`.*

`beta_sq` falls monotonically with refinement, in steps of `-504.75`, `-279.183`, `-175.237`,
`-121.369`, and `eps_eff` follows it down. The selection is stable: the mode does not change
identity as the mesh refines, and every rung kept exactly one criterion-passing column
(`n_eligible == 1` at all five rungs, `ok = True` at all five). What changes is `R_extracted`, and
it does not fall monotonically.

Row checks against 12.2: rung 1's `R`, `Q` and error reproduce the frozen note's roundings
(`3.780331990015745`, `1.345264977341367`, `34.5264977341367 %`), and rung 0's `Q` reproduces the
banked `1.440865461991999` exactly - the consistency check that this `Q` column is the note's own
quantity. Rung 3 agrees with the anchors already recorded in `decisions.md`
(`3.6127170293`, `beta_sq 96873.8886804`, `eps_eff 3.59392796`, `free_e 5044`).

**Why four of the five REPRO verdicts say FAIL, and why none of them is a fault.** From rung 1 up
the driver sets `C1_ALLOW_REMESH=1`, so the rebuilt mesh is not the banked mesh and the cache has
no column to check against. Rung 4's own log states the situation and its expected outcome
verbatim (`run.log:29`):

> WARNING : banked n_edges 1486 != rebuilt 9720: the mesh is not the banked one -- allowed by
> C1_ALLOW_REMESH=1; banked column unknown (-1), so the reproduction check below runs on the
> best-|corr_e_y| column and is EXPECTED to fail

and the check duly fails, at rung 4 by `rel_delta = 5.339e-02` on `e_y` (banked
`0.9207707848111418`, measured `0.96992994184837922`) and `rel_delta = 1.219e-03` on `e_z`
(banked `0.11916043239134175`, measured `0.11930571427583656`), with `cache_col = -1` and the
`REPRO R` line annotated `no anchor: resolved column 5133 is not the cache's identified column
-1`. Nothing about the solve failed: the run reports `rc=0`, `ok=True`, `modes_kept=1`, one
eligible column, and a residual of `1.844283662306968e-18` on 12807 degrees of freedom. The
reproduction check is a mesh-identity check, it is expected to fail on every re-meshed rung, and
it does. The comparison that matters - rung 0 against the banked capture - passed.

### 13.3 What the five rungs say about order, and why no order may be claimed

Using 12.3's convention (`h` proportional to `free_e^-1/2`, `p = ln(e_i/e_j) / ln(h_i/h_j)` with
`e = |R_extracted - R_analytic|`):

| interval | h ratio | h ratio, value | e before -> after | p |
|---|---|---|---|---|
| 0 -> 1 | sqrt(1444/2404) | 0.775026165625604 | 1.2388769776458042 -> 0.970229851263293 | 0.959071771078014 |
| 1 -> 2 | sqrt(2404/3604) | 0.8167231023860799 | 0.970229851263293 -> 0.7572062017739363 | 1.224455785196871 |
| 2 -> 3 | sqrt(3604/5044) | 0.8452882891841572 | 0.7572062017739363 -> 0.8026148905369874 | **-0.3465031741550254** |
| 3 -> 4 | sqrt(5044/9604) | 0.7247053430434572 | 0.8026148905369874 -> 0.7653106144427468 | **+0.1478095839365937** |

*DERIVED FROM MEASURED - arithmetic on the five `R_extracted` values in 13.2; no new compute.*

The first interval reproduces 12.3 to 14 significant digits (`0.775026165625604` matches exactly;
its `p` is `0.959071771078014` against 12.3's `0.9590717710780169`, the difference being rounding
in 12.3's truncated intermediate `0.7831527010107066` - unrounded, `p` = `0.9590717710780145`),
which is the anchor showing that this arithmetic is the note's arithmetic.

Rung 4 lands on the other side of the reversal. Rung 2 is the minimum of `R`
(`3.5673083405263886`); rung 3 is `+0.0454086887630511` above it; rung 4 falls back by
`0.037304276094240585` and settles `0.008104412668810568` - `1.0703045814765 %` - above that same
rung-2 minimum. So the sign of the increment is **not stable**: `-0.2686471263825112`,
`-0.2130236494893567`, `+0.0454086887630511`, `-0.037304276094240585`, i.e. `p` runs
`+0.96`, `+1.22`, `-0.35`, `+0.15`. A four-interval ladder with one sign change and one
near-zero interval carries no convergence order, and the least-squares version says so as loudly
as the differences: in log-log over rungs 0 to 4 the slope is `-0.2508` (the driver's FIT (a),
`p = -0.2508`, `c = +1.9373`) with `rms(log residual) = 0.0959`, against `0.0141` over rungs 0 to
2 - the residual has grown by a factor of seven as the extra rungs were added. Written in the
`h`-convention that is `p = 0.5015`, and it is quoted only as a diagnostic, as FIT (a) itself
insists: with sign-alternating deltas at this size `p` is not identifiable.

**The pre-registered extrapolants and the prediction they made.** Fitting `R` against
`1/free_e` and against `1/sqrt(free_e)` on rungs 0 to 3 (this is what the table in 12.6 and the
draft's tables record, and it is the state of knowledge before rung 4 existed) and evaluating at
`free_e = 9604` gave:

| fit window | variable | intercept = R as free_e -> inf | rms | R^2 | predicted R at 9604 |
|---|---|---|---|---|---|
| 0-3 | `1/free_e` (pre-registered variable) | **3.36584109881959** | 0.04410886472597009 | 0.945391 | 3.4674505912339324 |
| 0-3 | `1/sqrt(free_e)` | **2.990608605836237** | 0.05366950140373725 | 0.919152 | 3.392045140566151 |
| 0-4 | `1/free_e` (post-rung-4 refit) | **3.4280430184441846** | 0.053055969383763425 | 0.915997 | 3.5171301888940514 |
| 0-4 | `1/sqrt(free_e)` (post-rung-4 refit) | **3.182499977518278** | 0.07283622950403419 | 0.841686 | 3.49358848825005 |

*DERIVED FROM MEASURED - least-squares fits to the same five measured `R_extracted` values.*

Measured at rung 4: `3.575412753195199`. That is `3.1135890511087894 %` above the `1/free_e`
prediction and `5.405812865993953 %` above the `1/sqrt(free_e)` prediction, and it lies above the
whole envelope of the six pre-rung-4 fits - `[3.258799252188066, 3.4773906761129343]` - by
`2.8188399352308435 %` over the top of it (13.5). The prediction missed, in the direction that
says the fitted trend is not the trend the data follow.

The refits absorb rung 4 and move the asymptotes up, both of them now above the band ceiling:
`3.4280430184441846` is `+10.899981216472643 %` above `3.09111235262770` and
`3.182499977518278` is `+2.9564640318845425 %` above it. The refit's own residuals are not small
(`rms 0.053055969383763425`, `R^2 0.915997` for `1/free_e`; `rms 0.07283622950403419`,
`R^2 0.841686` for `1/sqrt(free_e)`), and the fit quality fell when rung 4 was added to the first
and to the second alike. That is the arithmetic signature of a plateau: extra refinement adds
scatter around a floor rather than approaching a limit.

### 13.4 The registered rule, applied without adjustment

The decision rule was fixed before any rung of this ladder ran, and it is quoted verbatim here as
it is in 12.6, from `tools/host/sparse-probe/evidence/ladder/summary_HIGHRES.txt`:

> (d1) |R_extracted - R_analytic| falls monotonically and the 1/n_free extrapolant lands
>      inside the band  ->  the discrepancy is discretisation, and the bar can be met by
>      a run at the fitted resolution;
> (d2) it is flat or non-monotone, or the extrapolant stays above 3.09111235262770
>      ->  the mesh is NOT the mechanism, and the ladder has eliminated it.

Both halves of `(d1)` are now tested against five rungs, and both fail.

**Monotonicity: fails.** `|R - R_analytic|` per rung is `1.238877`, `0.970230`, `0.757206`,
`0.802615`, `0.765311`, with steps `-0.268647`, `-0.213024`, `+0.0454087`, `-0.0373043`. One step
rises, and the minimum of the sequence is at rung 2 - not at the finest rung - with rung 4
`1.0703045814765 %` above it. Rung 4 does not restore monotonicity; it does not even return to the
floor. The summary's own step 4 prints exactly this and branches on it: `non-increasing with
refinement: NO` followed by `-> branch (d2) the mesh is NOT the mechanism: refinement has been
eliminated`.

**The `1/n_free` extrapolant: fails too.** On the pre-registered window (rungs 0 to 3) the
intercept is `3.36584109881959`, which is `8.887698499808593 %` above `3.09111235262770`. On the
full ladder it is `3.4280430184441846`, `10.899981216472643 %` above - the refit moved the
asymptote further out of the band, not into it. Adding the largest rung made the extrapolant
half of `(d1)` worse, which is the opposite of what `(d1)` needs.

*DERIVED FROM MEASURED - the percentages in 13.4 are arithmetic on the 13.2/13.3 tables and the
registered band edges; no new compute.*

Therefore **(d2) fires**, on both halves of the evidence independently, and the ladder has
eliminated this mesh family as the mechanism behind the 27 % amplitude discrepancy.

**A caveat on the rule's wording, to be fixed in this note and not resolved after the fact.**
`(d1)`/`(d2)` name `1/n_free`, while 12.3 orders in `1/h`, i.e. in `free_e^-1/2`, and the two are
not the same variable. The distinction is not academic here: the pre-registered
`1/sqrt(free_e)` intercept, `2.990608605836237`, is **inside** the band, `3.251377993621818 %`
below the ceiling, so on that variable the extrapolant half of `(d1)` would pass. What the
variable choice does **not** change is the branch: `(d1)` is a conjunction, and its monotonicity
half fails under either variable and with either fit window, so `(d2)` is the answer whichever
variable is read. The ambiguity is nevertheless a genuine defect in the registered text and
should be repaired there - named, not decided post hoc from rung-4 data, which is exactly what
`summary_HIGHRES.txt` prohibits:

> POST-HOC USE OF A NUMBER FROM THIS LADDER TO MOVE THE BAR IS A BREACH, not a correction.

### 13.5 What was predicted, and what happened

Six pre-rung-4 extrapolations were available - three fit windows (0-1, 0-2, 0-3) times two
variables - and all six predicted `R` at `free_e = 9604` inside

    [3.258799252188066, 3.4773906761129343]      (EXTRAPOLATED, pre-rung-4)

which is `5.424807655982433 %` to `12.496418098710205 %` above the band ceiling. So **no
extrapolation predicted a passing rung 4**: the whole predicted range was out of band before the
run. Measured `3.575412753195199` sits `2.8188399352308435 %` above the top of that range. The
outcome is therefore neither a confirmation of any of the six nor a discriminating result between
them; it says the trend the fits encode is not the trend the ladder follows.

For completeness, the better of the two pre-rung-4 stories - Scenario A, decay continuing at
`p` near 1 - would have reached the band edge only far outside the ladder. Anchoring at rung 0
with `e_0 = 0.440865461991999` and requiring `|Q - 1| <= 0.10`:

    p = 1.076558672005238 : free_e = 1444 * (0.440865461991999/0.10)^(2/1.076558672005238)
                                   = 22726.92343771123
    p = 0.959071771078014 : free_e = 1444 * (0.440865461991999/0.10)^(2/0.959071771078014)
                                   = 31854.49007059756

Under the note's own cost model (`peak RAM ~ 5.5*8*free_e^2` bytes, `wall ~ 45 s*(free_e/1444)^3`,
12.5) those two resolutions are **EXTRAPOLATED** to

    free_e = 22726.92 : 22.726574153517873 GB peak, 48.733811598855915 h
    free_e = 31854.49 : 44.64717565694314 GB peak, 134.19007791535472 h

and that is 2.37x to 3.32x the rung-4 free-edge count. Scenario A was therefore never a cheap
escape even in its own terms, and it is the story rung 4 refuted anyway.

**What a plateau looks like in one line, MEASURED.** Rung 2, at `free_e = 3604`, sits
`15.405327712979533 %` above the band ceiling. Rung 4, at `9604` - `2.67x` the free edges, `24.17x`
the wall clock (`9784.3` s against `404.8` s) - sits `15.667512057780897 %` above it: `0.2622`
percentage points **worse**. Quadrupling the work moved the operand in the wrong direction by an
amount far too large to be timing noise and far too small to be progress. That is the plateau,
and it is why the plateau branch is the one the rule returns.

### 13.6 The sparse cross-check at the largest rung

One solve, at the rung-4 mesh, by the sparse path (Route C), scored against the dense answer at
that same mesh. Same mesh, same physics, same selection and extraction rules, different linear
algebra: a shift-invert eigenproblem on an enlarged pencil, with a sparse LU factorisation of a
`12807 x 12807` operator (`12807 = 9604` free edges `+ 3203` free nodes) at
`nnz_S = 144151`, i.e. `8.788663579358298e-04 n^2` - the operator is never formed densely.

Agreement, **MEASURED** (`evidence/t4/rung4_routeC_report.json`):

| quantity | sparse | dense | relative difference |
|---|---|---|---|
| `beta_sq` | 96752.51970086167 | 96752.51970055024 | 3.218784779622725e-12 (11.49 digits) |
| `R_extracted` | 3.5754127532015456 | 3.575412753195199 | 1.77503391525794e-12 (11.75 digits) |
| `eps_eff` | 3.5894252835407867 | 3.5894252835292333 | 3.218739483580933e-12 |
| `corr_e_y` | 0.9699299418485792 | 0.96992994184837922 | 2.00e-13 |
| `corr_ez_vv` | 0.9665079165495085 | 0.96650791654718 | 1.32e-13 |

The solve's own diagnostics agree: Rayleigh quotient on the true pencil `96752.51970085397`,
residual `9.379388877240471e-13` and residual inside the enlarged pencil
`2.328122901161473e-18`, and the enlarged-pencil half of the eigenvector matching the dense
`Dc^T x1` to `3.016493594052664e-13`. The shift was `sigma = 96777.0147917196`, and `eigsh`
converged in 21 `OPinv` calls.

Cost, **MEASURED** at this mesh: sparse LU `0.05359245603904128` s (a second run read
`0.07401308696717024` s - at this size the difference is noise, and both are quoted rather than
the friendlier one), factor `nnz` 1369259, fill `106.91489029437027` per row, factor memory
`0.016431108` GB, `eigsh` `0.056758934049867094` s, wall `1.955740` s (second run `2.168797` s),
peak RSS `237.9` MiB, i.e. `ru_maxrss` ~243.6e3 KiB (known only to the log's four printed significant
figures; pinned to `[243637, 243660]` KiB by its two roundings) = `0.2324` GiB = `0.2495` GB decimal;
the log's `237.9 MB = 0.2324 GB` is binary multiples for both, labelling the second one GB (read from
`RUSAGE_CHILDREN`; no `/usr/bin/time` here; tracked in `evidence/t4/rung4_routeC_peak_rss.json`). Against the dense
rung's `9784.3` s that is

    9784.3 / 1.955740 = 5002.863366296133      (second run: 4511.395026828237)

for the same answer at the same mesh. Neither dense `B` nor dense `D` is ever formed - the
`0.687 GiB` matrix and the `82.07` MB matrix the dense path needs - and the report's own
`factor_is_effectively_dense` is `false`.

**Two caveats, both of which bound the claim rather than weaken it.** First, this is a
single-mesh ratio, not a scaling law: it is measured at `free_e = 9604` and it must not be
extrapolated as though the two paths scaled alike. Second, and more important, the shift is not
free information: `sigma = 96777.0147917196` is `0.999 x` the rung-3 `beta_sq` (`96873.8886804`),
so Route C is handed, to within `0.1 %`, the eigenvalue the ladder had already localised. The
dense path, as the ladder runs it, finds the mode with no such bracket. The speed-up therefore
compares two ways of obtaining the same object, not two equal amounts of work, and the honest
statement is that the sparse path is **validated** at the largest rung and **cheap when
bracketed** - not that it replaces the dense ladder as a blind search.

One defect recorded, not fixed, in the manner of 10.9: `rung4_routeC_probe.py:858` raises
`KeyError: 'n'` in `print_summary` after the report has been written, so the probe exits non-zero
while its report carries `verdict.overall.exit_code = 0`. The numbers above are read from the
written report and are unaffected; the printed summary is.

### 13.7 The verdict

`T4_amp: FAIL`, unmoved, and unmoved for a reason the ladder now supplies rather than assumes.
`R_extracted = 3.575412753195199` at the finest mesh, `Q = 1.2723426326355907`, so

    |Q - 1| = 0.27234263263559066       allowance 0.10

i.e. `2.7234263263559066x` the allowance, with `R_extracted` `15.667512057780897 %` above the
band's upper edge `3.09111235262770`. Nothing in 13 softens that, and nothing in 13 is scored
against a moved bar: `R_analytic`, the band, and the column-selection rule are all as 9.2 and
9.7 left them.

The attribution is `(d2)` (13.4): this mesh family is eliminated as the mechanism. That is a
narrower statement than it may look, and the narrowness is the point. It does not say the
discrepancy is physics; it says refinement in this family does not remove it, and five rungs and
a 510x span in `free_e` (`1444` to `9604`), costing 3.22 h, are enough to say that. It does not
localise what does remain: strip, `y_air` and `z` move together at every rung, so `(d2)`
eliminates *this family*, not every mesh parameterisation - 9.7 and 9.8 remain the only evidence
that the strip and air bands are individually flat. And it does not touch 10: the extraction is
still correct, and `Q = 1.440865461991999` at the banked resolution still stands.

What is left standing after the ladder is a discrepancy of 27.2 % that is neither a mesh artefact
nor an extraction defect, and the next question is therefore not another refinement - it is what
else in the model behind `R_analytic`, or in the physics of the `e_y` denominator (10.6), differs
from the measurement. The ladder's contribution is to have closed the cheapest explanation with
evidence rather than by assertion.

### 13.8 Provenance, and one honesty note about the rule's timing

Every number in 13 is read from an artefact or is arithmetic on such a number, and the arithmetic
is reproducible from `evidence/t4/ladder_convergence.json` (`schema: t4.ladder_convergence/v1`),
which carries the five rung records, the pre-registered and post-rung-4 fits, and the Route C
cross-check with their definitions.

- `tools/host/sparse-probe/out/summary_HIGHRES.txt` - `21562` B, mtime
  `2026-10-28T01:51:17.495874934Z`; scores all five rungs and prints both verdicts (13.2, 13.4).
- `tools/host/sparse-probe/out/rung0_s12_a9_z8-4-4/` ... `rung4_s36_a22_z20-10-10/` - per rung
  `run.log`, `env.json`, `c1_table.txt`, `c1_spectrum.npz`. The rung-4 npz is `738560423` B; its
  `run.log` is `6773` B and its `DONE` line is at `:71`.
- `tools/host/sparse-probe/out/prev/` - the earlier, unanchored pass's rung 0 and 1 directories,
  parked rather than deleted; the source of the two wall clocks 13.1 supersedes.
- `evidence/t4/rung4_routeC_report.json` - sha256
  `593b1117edc171da25b850eec12819127402b6a2f34c4007c3ed62a243933398`; the Route C record (13.6).
- `evidence/t4/rung4_dense_anchor.json` - `2159` B, md5 `d9c1d3f9178f25fa526b7aea93611c05`; the
  dense rung-4 anchor Route C was scored against.
- `docs/design/t4_s13_draft.md` - `13793` B, `205` lines, mtime
  `2026-10-28 01:52:01.035717862`; the draft this section replaces, now marked SUPERSEDED.

**The honesty note.** The decision rule quoted in 13.4 was written before any rung of this ladder
ran, and that is the claim made for it - not for the draft. The draft's mtime,
`2026-10-28 01:52:01.035717862`, is `43.5` s **after** the rung-4 job's own `DONE` line
(`01:51:17`, `elapsed=9784.3s`) and after `summary_HIGHRES.txt` was written
(`01:51:17.495874934Z`). It is therefore **not** a timestamped pre-registration and is not cited
as one. What is true of it is weaker and still worth stating precisely: its content predates
knowledge of the rung-4 value - it records rung 4 as pending, quotes no rung-4 number, and
proposes thresholds rather than applying any - so it is a rule fixed without knowledge of the
result, which is not the same thing as a pre-registration stamped before the result existed. Only
the `(d1)`/`(d2)` block in `summary_HIGHRES.txt` carries the stronger warrant, and it is that
block, not the draft, on which 13.4's reading rests.

One false alarm belongs on the record here: the `indefinite` / `LinearOperator` material is not in
this note and never was - it lives in `docs/design/sparse_eigenmode.md`, where `indefinite` appears
on `16` lines and `LinearOperator` on `6` - so a grep of this note for it finds nothing, and
that absence is not a loss.
