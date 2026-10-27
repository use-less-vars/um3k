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

`A_ez = PANA.e_z` on y(nodes)×z(cells), `A_ey = PANA.e_y` on y(cells)×z(nodes) (`c1_audit.py:430-433`, guard `:437-441`, banked `:632`). Both arrays are **array-identical** (`np.array_equal` = True) between `c1_spectrum.npz` and `pecbox_spectrum.npz` — the two files are not byte-identical, they differ everywhere else — so `R_analytic` is one number and cannot separate the PMC leg (col 738) from the PEC leg (col 699). The extracted side can: it is banked as a scalar, `R_extracted = 4.0489791163982565`, which is `1.440865×` `R_analytic`, and §2 is now about the column it was taken on.

## 2. The artefacts, named: `R_extracted` is banked, the arrays behind it are not

Both readings are in the two captures (`tools/host/c1-audit/out/` — the `out/` of §1's table is relative to that directory), and the arrays that formed the second one are still not saved. `c1_spectrum.npz` (16,972,501 bytes): `lam` (1444,), `j = [738]`, `bank_col` 738, `R_extracted` 4.0489791163982565, `beta` 312.78276463, `corr_ey` 0.92077078, `corr_ez_vv` 0.93528673, `A_ez` (201,76), `A_ey` (200,77), `ok` [True]. `pecbox_spectrum.npz` (15,568,904 bytes): `lam` (1382,), `j = [699, 704]`, `bank_col` 738, `R_extracted` 70.635018555128326, `beta` [311.77211206, 86.93931629], `corr_ey` [0.91234304, −0.42641899], `corr_ez_vv` [0.93692972, −0.08313435], `ok` [True, False]. What is **not** banked is the pair the scalar was reduced from: `c1_audit.py:513-514` builds `e_y = e_at(_ey_pts)[:,:,0]*CELL`, `:520-521` builds `e_z_vv = e_at(_ezc_pts)[:,:,1]*CELL`, `:528-534` reduces each to a scalar, and `:609-635` banks only `A_ez`, `A_ey` and scalars. `.scratch/e_z_signed_41x22.npz` does not hold them either: `e_z_raw`/`e_z_plane` are **longitudinal** (`-interp(beta*z_free)`, `c @ z_free`), not the vertical one.

Not one script's oversight: every artefact that pairs the two fields normalises each by its own norm first — `c1_audit.py:528-534` (correlation), `.scratch/d22_t3_regions.py:69-74` (`_unit_pair`: `A/|A|`, `E/|E|`) — so the amplitude ratio is divided out by construction wherever the pair was analysed. The record says the same at `decisions.md:7956`: "What the true vertical-over-in-plane energy ratio is has not been computed." *`decisions.md:7956` is the pre-extraction record; the banks are ahead of it, they do not contradict it: the ratio is banked as a scalar, the fields behind it are not.* What remains open is the **column**: 738 (the peak, `ok` True) gives 4.0489791163982565, 704 (the last leg scanned, `ok` False) gives 70.635018555128326 — a factor 17.445142719817547. A ratio quoted without its column is not a measurement, and §9 makes recording it a precondition of scoring. Two points are inference rather than record and are marked so: that 70.635 belongs to column 704 (the PEC file's own `bank_col` is 738, so the attribution rests on `j = [699, 704]` beside `ok = [True, False]`), and that `R_extracted` was formed at run time from the un-reduced fields rather than from the banked arrays (forced, since `A_ez`/`A_ey` are array-identical across the two files while their `R_extracted` differ by 17×). Neither needs a re-run to settle the gate.

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
- **Miscite:** `decisions.md:7948` puts the `e_z_vv` read at `c1_audit.py:510-511`; the construction is `:520-521`.
- **Duplicate captures:** `TOLFLUX.json` and `TOL.json` carry identical `beta`/ephemera but differ on `poynting` (True/False) and `wall` (4210.48/4560.05).
- **Open tension, unresolved here:** 4.52 % (fail by 9x) and 0.40 % (pass) are both "beta against 312.7827646322591". Which fit T2 is scored on is not settled by the banks; naming the estimator is a precondition, as `decisions.md:7680` already warns.

## 9. `T4_amp`: the pass condition it will have to be scored against (registered, not implemented)

**Registered, not implemented.** The bar has a ruling of record — §9.2 is ADOPTED and LOCKED and the entry is in `decisions.md` — so `T4_amp` is no longer a proposal. Nothing in this section is enforced: no `.py` file compares `R_extracted` against `tol_rel`, no gate entry appears, and `m3c_gate_v2.md:630` still reads "Seven entries, no more." The section fixes what `T4_amp` asserts, and what it must establish before it is allowed to assert it. The bar is **a pre-registered engineering requirement, not a derived error budget** — nothing in the record measures the scatter of `R_extracted` on this design, so nothing in the record can derive a tolerance from it.

### 9.1 The scored quantity

`Q = R_extracted / R_analytic`, scored as the inequality `|Q − 1| <= tol_rel`, with both operands read from the banks: `R_analytic = 2.810102138752` (§1, `sum(A_ez^2)/sum(A_ey^2)`, one number because the two arrays are array-identical across the captures) and `R_extracted = 4.0489791163982565` from the **PMC leg, column 738**, whose `ok` is `True` and whose capture's `bank_col` is 738. Today `Q = 1.440865461991999`.

- **The PMC leg is the scored leg.** Column 738 is the peak column of `c1_spectrum.npz` (`j = [738]`, `ok = [True]`) and the column §6/§7 read `beta` on (`beta_eigen = 312.7827646322591`), so scoring and the beta record sit on the same column.
- **The PEC reading is named as a wrong-column artefact and is excluded from scoring.** `pecbox_spectrum.npz` also carries an `R_extracted`, 70.635018555128326, and it is not a second physics result to be compared: its leg list is `j = [699, 704]` with `ok = [True, False]`, its own `bank_col` is 738, and 70.635018555128326 is 17.445142719817547× the peak-column value. It is retained as the diagnostic of column sensitivity in §9.4, and not as a data point. *Inference, marked as inference:* attributing 70.635 to column 704 rests on the leg list beside `ok`, not on the file's `bank_col`.
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

`R_extracted` is knife-edge sensitive to the column it is read on — 4.0489791163982565 at 738 against 70.635018555128326 at 704, a factor 17.445142719817547, because the extraction reduces per column and column 704 is a non-carrier (`ok` False). A bar applied to a number that can move by 17× on a selection the record does not pin down is not a test of anything. So `T4_amp` will require, before it compares anything:

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
| 5 | stored PEC `R_extracted = 70.635018555128326` is the *last scanned* failing-witness column, 704 (`corr_ey = -0.426418989`, `corr_ez_vv = -0.083134346`) | the identified column 699's `R = 4.1636565248` exists in no artefact | the PEC leg's quotable `R` is **unbanked**; any future PEC scoring must re-derive it |
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
(header, §1–§8) are out of scope by instruction and are untouched — their own
stale cites are listed at the end of this section so a reader is not misled
into trusting them. Line count is unchanged (256 lines; no edit moved text
across a line boundary), and the first 51 lines hash byte-identically before
and after (`head -51 | sha256sum` = `4abbadd18c77018758db6a74ea4393ce761fb916aab62db724fa524307a80f54`,
computed with the same method on both sides).

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

### 11.4 Deliberately left stale

- **§1–§8 (lines 1–51), frozen.** These still cite `c1_audit.py:430-433`,
  `:437-441`, `:632` (§4), `:513-514`, `:520-521`, `:528-534`, `:609-635`
  (§5), `:528-534` (§6). Under the current mapping the two field builds are
  `:679-680` and `:686-687` and the reduction is `:746-747`; the guard and
  banking sites have moved comparably. Read §1–§8 for the argument and §9–§11
  for line numbers.
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
