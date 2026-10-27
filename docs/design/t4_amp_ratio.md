# T4 — the amplitude ratio: `R_analytic` is banked, `R_extracted` is not

Arithmetic on banked arrays only. No solve, no gate run, no field reconstruction.

## 1. Result

| quantity | value | source |
|---|---|---|
| `sum(A_ez^2)` | 3.036149093425e+02 / 15276 pts, rms 1.409797455137e-01 | `out/c1_spectrum.npz:A_ez` (201,76) |
| `sum(A_ey^2)` | 1.080440832223e+02 / 15400 pts, rms 8.376066833477e-02 | `out/c1_spectrum.npz:A_ey` (200,77) |
| **`R_analytic`** | **2.810102138752** | quotient of the rows above |
| `R_analytic`, per-sample | 2.832912603875 | `mean/sq`, n-gap 15400/15276 = 1.008118 |
| amplitude ratio | 1.676336 (per-sample 1.683126) | `sqrt` of both |

`A_ez = PANA.e_z` on y(nodes)×z(cells), `A_ey = PANA.e_y` on y(cells)×z(nodes) (`c1_audit.py:430-433`, guard `:437-441`, banked `:632`). Both arrays are **byte-identical** between `c1_spectrum.npz` and `pecbox_spectrum.npz` (`np.array_equal` = True), so `R_analytic` is one number and cannot separate the PMC leg (col 738) from the PEC leg (col 699). Only the extracted side could, and that side is missing.

## 2. `R_extracted` cannot be formed; the absent arrays are named

`sum(e_z_vv^2)/sum(e_y^2)` needs `e_y` (200,77) and `e_z_vv` (201,76). Neither is banked: `c1_audit.py:513-514` builds `e_y = e_at(_ey_pts)[:,:,0]*CELL`, `:520-521` builds `e_z_vv = e_at(_ezc_pts)[:,:,1]*CELL`, `:528-534` reduces each to a scalar (`corr_ey` 0.92077078; `corr_ez_vv` 0.93528673 PMC col 738, 0.93692972 PEC col 699 — its second entry −0.08313435 is the non-carrier column 704), and `:609-635` saves only `A_ez`, `A_ey` and scalars. `.scratch/e_z_signed_41x22.npz` does not hold them either: `e_z_raw`/`e_z_plane` are **longitudinal** (`-interp(beta*z_free)`, `c @ z_free`), not the vertical one.

Not one script's oversight: every artefact that pairs the two fields normalises each by its own norm first — `c1_audit.py:528-534` (correlation), `.scratch/d22_t3_regions.py:69-74` (`_unit_pair`: `A/|A|`, `E/|E|`) — so the amplitude ratio is divided out by construction wherever the pair was analysed. The record says the same at `decisions.md:7956`: "What the true vertical-over-in-plane energy ratio is has not been computed." Recovering it means re-running `c1_audit.py` or `mode_plot.reconstruct_run` (2 sparse assemblies + 2 LUs) — reconstruction, out of scope here. **Absent: `e_y` (200,77) and `e_z_vv` (201,76).**

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
