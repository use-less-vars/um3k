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

## 9. `T4_amp`: the pass condition it will have to be scored against (design only)

**Design only.** Nothing in this section is implemented, registered, or run: no `.py` file changes, no gate entry appears, and `m3c_gate_v2.md:630` still reads "Seven entries, no more." The section fixes what `T4_amp` will assert, and what it must establish before it is allowed to assert it. The bar proposed here is **a pre-registered engineering requirement, not a derived error budget** — nothing in the record measures the scatter of `R_extracted` on this design, so nothing in the record can derive a tolerance from it.

### 9.1 The scored quantity

`Q = R_extracted / R_analytic`, scored as the inequality `|Q − 1| <= tol_rel`, with both operands read from the banks: `R_analytic = 2.810102138752` (§1, `sum(A_ez^2)/sum(A_ey^2)`, one number because the two arrays are array-identical across the captures) and `R_extracted = 4.0489791163982565` from the **PMC leg, column 738**, whose `ok` is `True` and whose capture's `bank_col` is 738. Today `Q = 1.440865461991999`.

- **The PMC leg is the scored leg.** Column 738 is the peak column of `c1_spectrum.npz` (`j = [738]`, `ok = [True]`) and the column §6/§7 read `beta` on (`beta_eigen = 312.7827646322591`), so scoring and the beta record sit on the same column.
- **The PEC reading is named as a wrong-column artefact and is excluded from scoring.** `pecbox_spectrum.npz` also carries an `R_extracted`, 70.635018555128326, and it is not a second physics result to be compared: its leg list is `j = [699, 704]` with `ok = [True, False]`, its own `bank_col` is 738, and 70.635018555128326 is 17.445142719817547× the peak-column value. It is retained as the diagnostic of column sensitivity in §9.4, and not as a data point. *Inference, marked as inference:* attributing 70.635 to column 704 rests on the leg list beside `ok`, not on the file's `bank_col`.
- **n = 1.** One capture per leg, one column, one run. There is no empirical scatter in the record for this quantity, and none is assumed below.

### 9.2 The bar: ±10 % relative, and the absolute band it implies

Primary proposal: `tol_rel = 0.10` on the scored inequality, i.e. `Q ∈ [0.90, 1.10]`. Converted into the quantity's own units in Python from the two banked numbers (not by hand), that band is `R_extracted ∈ [2.52909192487721, 3.09111235262770]`.

"Over the limit" below is `|Q − 1| / half-width`: 0 is exact agreement, 1.00 sits exactly on the limit, anything above 1.00 fails.

| bar | pass band on `Q` | pass band on `R_extracted` | half-width as % of `R_analytic` | `\|Q − 1\|` / half-width today | today |
|---|---|---|---|---|---|
| **±10 % relative (primary proposal)** | [0.90, 1.10] | [2.52909192487721, 3.09111235262770] | 10.000 % | **4.408654619919989×** | **FAIL** |
| ±20 % relative | [0.80, 1.20] | [2.24808171100196, 3.37212256650294] | 20.000 % | 2.2043273099599947× | FAIL |
| ±25 % relative | [0.75, 1.25] | [2.10757660406434, 3.51262767344057] | 25.000 % | 1.7634618479679958× | FAIL |
| ±0.2 absolute, on the ratio | [0.9288282097501301, 1.0711717902498699] | [2.61010213875245, 3.01010213875245] | 7.117179024986979 % | 6.1943848882290204× | FAIL |

Two things the table settles. **±0.2 absolute is proportionally *tighter* than ±10 % relative**, not a looser fallback: 0.2 is 7.117179024986979 % of `R_analytic = 2.810102138752`, so an absolute band that size admits only a 7.1 % relative disagreement on this geometry. And every candidate bar fails today — the loosest, ±25 %, still fails by 1.7634618479679958× — so the current reading is not a near miss under any tolerance on the list.

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

**Not registered, not implemented.** §9 changes no `.py` file, adds no gate entry, and edits no decision record. `m3c_gate_v2.md:630` still reads "Seven entries, no more."; when `T4_amp` is registered it becomes the eighth, and that line must be edited deliberately, as a separate act.

### 9.6 Revisit clause

The bar may be revisited **once**. The revisit must be pre-registered in `decisions.md` — the new tolerance, the mechanism that justifies it, and the date — *before* it is applied to any computed value. It must never be tuned post-hoc to a number already in hand: choosing the tolerance after seeing 1.4409 (or 1.763, or 6.194) converts the gate into a description of the result it was supposed to judge. A revisit prompted by a measured miss must therefore name a mechanism — a changed column-selection rule, a re-meshed run, a different leg, a resolved estimator question from §6 — and not merely a new number.
