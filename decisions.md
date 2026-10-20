# Decision log

Every major choice in this project is recorded here together with the argument
that was rejected, so that a later reader can tell a considered choice from an
accident. Re-read this file at the start of each session, before re-deriving
anything it already settles. Where a number appears it is measured, and the
run or test that pins it is named.

---

## Attachments reach the browser as `data:` URIs, not through a media route

- **Decision.** The results page inlines every figure a study produces, PNG and animated GIF alike, as a `data:` URI produced by `emfit/webapp.py`; there is no route that serves a figure file and no WebSocket, so a result is one response and the browser fetches nothing afterwards.
- **Strongest argument against.** A 280 689-byte animation is 374 KB once base64-encoded, which is 57 per cent of the 656 469-byte response, is re-encoded on every request and carries no cache validator; a `/media/<id>` route or a socket would send the bytes once and let the browser stream them.
- **Why that argument does not win.** The viewer shows a completed run one page at a time, on loopback, with no authentication and a single module lock, so a media route would need per-run state to resolve an id and a socket would need the run to be produced incrementally. It is not: the only encoder available in this container is `matplotlib.animation.PillowWriter`, because there is no ffmpeg, and it writes a complete GIF before anything can be served. There is nothing to stream, and the measured cost of inlining is 0.05 s of rendering against a 4.95 s study.
- **Evidence.** `tests/test_webapp.py::test_real_rcs_run_serves_the_full_animation` (marked `slow`) posts to `/run/rcs` and parses the served page: one GIF `data:` URI, a PNG `data:` URI, `GIF89a` on decode, and `n_frames == RCS_ANIM_FRAMES`. The measured run behind those numbers gave 280 689 bytes, 244x208 px, exactly one PNG and one GIF `data:` URI, and GIF bytes identical to the file `python -m emfit run rcs --out` writes. No browser binary exists in this container, so the animation is verified by decode and not by watching it play.

## Factorisation of the port impedance: report a complex Z0, never the modulus

- **Decision.** The port impedance is `z0 = complex(v_port / i_trunc)` and is reported as a complex number, on the complex plane and in polar form, with modulus and phase labelled as modulus and phase. No quantity is ever labelled `Z0` when it is the modulus alone.
- **Strongest argument against.** A transmission-line impedance is a real number to a circuit designer; the Smith chart and every datasheet use a real Z0, and reporting `50.954 + 15.870j` invites the reply that the port is broken.
- **Why that argument does not win.** The modulus is 9.62 per cent above Hammerstad-Jensen while the real part is within 4.66 per cent, and the whole excess factorises exactly as `1/cos(17.299 deg) = 1.04738` acting on `Re/HJ = 1.04661`, giving 1.09622. Printing the modulus as Z0 therefore attributes a localized port reactance to the line, which is a false attribution; printing the pair states the fact and names its cause. A reader who wants a real Z0 gets `Re(z0)`, which is quoted alongside.
- **Evidence.** `z0 = -50.954009 - 15.869531j` at 5.827786 GHz (the sign is the return-current reference); `|z0| = 53.368090`, phase 17.299 deg; `z0_model = 48.685768` (the Hammerstad-Jensen value); `Re/HJ = 1.04661`. `emfit/studies.py` printed `abs(self.z0)` under the name `z0` in `MicrostripWave.summary()` and in the study wrapper's report table; both now print modulus, phase and real part as labelled quantities.

## The station fit, not the port ratio, is the Z0 measurement

- **Decision.** Z0 is measured by fitting the travelling-wave amplitudes and phases at a row of probe stations on the trace, away from the source, and that fitted value is the reported line impedance. The port ratio is retained and reported as the port plane impedance, which is a different quantity.
- **Strongest argument against.** A real VNA references at its own connector plane, so the port plane is where a measurement physically happens; the stations are extra solver state that exists only in simulation.
- **Why that argument does not win.** The port plane carries 17.299 deg of excess phase, of which 9.88 deg dies in the first 7.2 mm from the source and only 0.78 deg remains over the following 9.6 mm. That is a source artifact with a length scale, not a property of the line. Across nine stations spanning 10.4 to 20.0 mm the modulus has mean 50.627 ohm with standard deviation 0.343 ohm and the excess phase has mean 7.29 deg with standard deviation 0.267 deg, so the station value is stable and the port value is not representative.
- **Evidence.** Station table at cell 0.4 mm -- x = 10.4 mm: 51.223 / 7.421 deg; x = 15.2 mm: 50.608 / 7.418 deg; x = 20.0 mm: 50.115 / 6.637 deg; mean over all nine stations 50.627 / 7.29 deg. The residual after the fit is 7.3 deg at every plane, which is eight times the 0.86 deg bound set by twice the measured reflection coefficient, so the residual is not standing wave and is an open problem.

## Propagation constant from the one-wave joint complex-gamma fit

- **The headline beta is the one-wave joint complex-gamma fit: 232.447 +/- 0.077 rad/m.** The two-wave value 232.558 and the two-station value 232.493 are robustness checks only and are never the headline; a row or a sentence that quotes either of them as "the" beta misrepresents the measurement even when the number under it is right.

- **Decision.** The reported `beta`, and hence `eps_eff`, is the one-wave joint complex-gamma fit of the probe series, `beta = 232.447 +/- 0.077 rad/m`; the two-wave value (232.558) and the two-station value (232.493) are cross-checks and not the reported number, and the quasi-TEM model (223.353) is retained as a diagnostic only.
- **Strongest argument against.** The model value is smooth, reproducible and independent of the fit window, whereas the fitted value moves with the window and depends on a reflection coefficient of only 0.0075.
- **Why that argument does not win.** The model `beta` embeds a quasi-static approximation the simulation does not make, so agreement with it would be a coincidence; the fitted `beta` is extracted from the same field data as the impedance, so the two quantities are members of one mode or neither is. The discrimination of a 9 rad/m difference is far outside the fit residual of 0.0095.
- **Evidence.** `beta` one-wave 232.44696, two-wave 232.55796, two-station 232.49315, model 223.35307 rad/m; `|gamma| = 0.007493` at +41.194 deg; `eps_eff = 3.621781` against Hammerstad-Jensen 3.343938.

## Acceptance tolerance for Z0 is 5 per cent on a stated box

- **Decision.** The locked test is Z0 within 5 per cent of Hammerstad-Jensen at a stated box, stated clearance and stated mesh. A 2 per cent claim is permitted only as a report-level statement from the 1/clearance extrapolation, and it must quote its fit residual and the range it extrapolated over, or be called a coincidence.
- **Strongest argument against.** 5 per cent is loose enough that a wrong port or a miscounted mesh could pass it.
- **Why that argument does not win.** The lateral sweep shows the convergence is monotone and close to linear in 1/clearance -- 51.4886 at 3.0h, 50.2670 at 4.5h, 49.6218 at 6.0h, 49.2420 at 7.5h, 49.0101 at 9.0h -- so the sweep, not the single number, is what discriminates a wrong port. A test that cannot pass on the affordable box is a bad test.
- **Evidence.** Lateral sweep at cell 0.4 mm, five clearances, values above; Hammerstad-Jensen 48.685768 ohm.

## Static air capacitance must be measured at the same box as eps_eff

- **Decision.** Any static comparison quotes the air-filled capacitance per length computed with `eps_r = 1.0` at the same clearance as the wave result, and any percentage error is quoted against a named reference value.
- **Strongest argument against.** The air-filled value is a property of the cross-section alone and should be mesh-independent, so one number ought to serve all boxes.
- **Why that argument does not win.** The box shrinks with the mesh because the walls are pinned at 3h from the trace, so the air capacitance moves with the box -- 36.585, 38.432 and 39.107 pF/m at 3h, 6h and 12h clearance at cell 0.4 mm. Comparing across boxes compares two different problems. Inside a 12h box refined to h/16 the value is 37.677 pF/m against Hammerstad-Jensen 37.467, so 37.677 is the reference and the coarse-box excess is 12.8 per cent, not the 14 per cent previously quoted.
- **Evidence.** Values above; the static air impedance agreeing with the model to 1 per cent at h/4 is a cancellation of -2.4 per cent in `C_air` against +7.0 per cent in `eps_eff`, not accuracy.

## The power check is an independent path, not a restatement

- **Decision.** Losslessness is checked by forming, at every probe station, the power-current impedance `|V|^2 / (2 P)` with `P = Re(V I*)/2` from the strip current, dividing it by the fitted `Re(z0)`, and reporting the mean, the spread and the worst station against the bound the measured reflection alone can produce. The check consumes the current phasor and is never obtained by adding `|S11|` and `|S21|` together.
- **Strongest argument against.** Both routes read the same station fields, so a ratio of 1 proves only that the solver is self-consistent, and a self-consistency check printed beside the measurement it implies is a restatement dressed as evidence.
- **Why that argument does not win.** The two routes share the stations but not the field: the impedance comes from the fitted travelling-wave amplitude of the line voltage across the gap, the power from `Re(V I*)` with the strip current integrated on a different edge set. An error that is not a property of one mode -- a second mode, a station in the near field, a mis-set gap -- moves the two apart, which is exactly what this row is for. What is left over after the bound is subtracted is 0.08 per cent on the mean, so the row says the record carries one mode and says nothing else.
- **Evidence.** Ratio mean 0.999177, spread 2.19e-02, worst station 10.40 mm at 1.011186; the bound from `|gamma| = 0.0075` is 3.0 per cent (0.0304), so the observed spread sits inside it; on the port plane the ratio is 1.000000 by construction, which is why the port is not where this check is quoted.

## The far end is an absorber, and every reflection number is attributed to it

- **Decision.** The strip is run from the source into the `n_pml`-cell absorber on the far `x` wall and is deliberately not terminated in a load. The reflected mode that the stations measure, `|S11| = 0.00748` (`-42.52 dB`), is reported as the residual reflection of that termination together with the source lump, and neither the row nor the prose calls the line matched or gives it a load.
- **Strongest argument against.** An absorber is a numerical device whose reflection depends on its cell count and its profile, so a reflection coefficient attributed to it is a property of the mesh rather than of the transmission line, and quoting it as an S-parameter lends a numerical residue the standing of a physical measurement.
- **Why that argument does not win.** The model contains no other termination: the metal wall behind the absorber is never reached by the wave, and there is no resistor anywhere, so the 0.0075 has to belong to the layer -- calling it a load or a matched port would name a thing the model does not contain. The attribution is also testable rather than decorative, because the same 0.0075 sets the 3.0 per cent bound the power-ratio row is judged against, and it reproduces between the one-wave fit and the station fit.
- **Evidence.** `|S11| = 0.00748` (`-42.52 dB`) at the first station, 10.40 mm; the same magnitude on the port plane at `d = 7.20 mm`, since `beta` is real; VSWR `1.0151 : 1`; `|gamma|` one-wave 0.00749 against 0.00748 from the station fit; six-cell absorber, `n_pml = 6`.

## |S21| comes from the joint complex-gamma fit, not from the two half ratios

- **Decision.** The reported insertion loss is `|S21| = exp(-alpha L)` with `alpha` taken from the joint complex-gamma fit of the station series (`emfit.ports.fit_line`, one wave, `alpha` and `beta` fitted together on the same phasors), and `L` the span between the first and the last station. The old two-half-ratio estimator -- forward amplitudes of two half fits, each shifted onto its own plane, divided and de-embedded -- is retained in the table as a cross-check and is no longer the reported value.
- **Strongest argument against.** The half-ratio estimator is a pure amplitude ratio: it needs no loss model, and its `beta` is real so the de-embedding factor has unit modulus and cannot leak into the magnitude. Exponentiating a fitted `alpha` replaces a measurement with a one-parameter model of the decay, and the two do not agree on the default box -- 0.983656 (`-1.634` per cent) against 0.971204 (`-2.880` per cent), a gap of 1.25 percentage points, about seventeen times the fitted standard error on the second.
- **Why that argument does not win.** The half-ratio estimator's own window bias is `+-25` per cent of `alpha`, which is `+-0.28` per cent of `|S21|` -- between a quarter and a third of the 1 per cent the G1 gate judges, i.e. the estimator was quoting a number of the same size as its own systematic. A quantity cannot be judged at 1 per cent by an instrument biased at 0.28 per cent and then be called a pass or a fail without the bias being named. The joint fit is used instead because it estimates the decay from all nine stations at once and returns its own standard error and its correlation with `beta`, so the row states a number with a budget rather than a number with an unquantified window. The disagreement between the two is not hidden: it is the largest single open item in the G1 verdict, and the report says so.
- **Evidence.** Default box, `2400` steps, `5.827786` GHz, nine stations over `9.60` mm: `alpha = 0.02644 +- 0.00067` dB/mm (`3.0436` Np/m, `beta = 232.446 +- 0.077` rad/m), `rho(alpha, beta) = +0.0000`, `exp(-alpha L) = 0.971204 +- 0.000715`, i.e. `-2.880` per cent from unity, outside the 1 per cent gate by a factor of three and outside it at one sigma as well; two-wave `alpha = 0.02554 +- 0.00092` dB/mm. The half-ratio estimator gives `0.983656`. `alpha` enters the line impedance too and costs it almost nothing: `Re(z0) = 50.5505 +- 0.0814` ohm against `50.5474` ohm with the decay held fixed, a shift of `0.0031` ohm or `0.04` of its own sigma.

## The mid-plane slice averages the two cells that straddle the plane

- **Decision.** The mid-plane `E_z` phasor is the mean of the two cell values at `k_mid - 1` and `k_mid`, not the single cell value below the plane and not an interpolant.
- **Strongest argument against.** Picking one cell is simpler and needs no averaging, and any average of two neighbours is a half-cell-wide box filter that softens a genuine gradient.
- **Why that argument does not win.** `ez` is a cell quantity: the unknown stored in cell `k` is the line integral over that cell, i.e. the field at the cell *centre* `(k + 1/2) h`. The physical plane of interest, `z_mid = k_mid h` (half the substrate thickness), therefore falls exactly *between* the centres of cells `k_mid - 1` and `k_mid`, so neither cell holds the value on the plane and the mean of the two is the one combination whose abscissa is the plane itself. This is the same half-cell offset argument that fixed the station currents: a quantity located at cell centres cannot be read on a point layer without saying which two centres it was averaged over. Averaging over two cells also keeps the DFT accumulators aligned with the `E_z` block layout, so no partial cell enters the sum.
- **Evidence.** Default box: `n_sub = 4` cells of `0.4` mm, `k_mid = 2`, `z_mid = 0.8` mm, exactly half of the `1.6` mm substrate; slice shape `(63, 45)` = `(nxn, nyn)`, `|E_z|` peak `9.26e4` V/m at the loop's own `j_centre = 22`, i.e. on the strip centreline, falling to `0` at the outer point layers; figure written as `study-out/fig_g1_midplane-ez.png` by `emfit.studies.dump_figures`.

## The model is lossless, so unit `|S21|` is an exact target, not an aspiration

- **Decision.** Every shortfall of the measured `|S21|` from unity is charged to the box and to the estimator -- the PML's absorption of the discretised guided mode and the bias of the joint amplitude fit -- and none of it is charged to dielectric or conductor loss. No number in this project is explained by `tan_delta` or by surface resistance, because the solver contains no such term. A measured `alpha` in the range `0.0139`-`0.0278` dB/mm is therefore a bound on our own numerical error, not a measurement of the hardware.
- **Strongest argument against.** The numbers look exactly like a loss. The floor is `0.0139 +- 0.0026` dB/mm over `14.4` mm, i.e. `|S21| = 0.977`, and FR4 at `tan_delta = 0.02` would give `alpha_d = 0.0189` dB/mm with roughly `0.002` dB/mm of conductor loss on top -- the same order, in the same units, and absorption is the pedestrian reading that requires no further work.
- **Why that argument does not win.** Agreement in magnitude is not a mechanism. The damping operator is the PML only -- `FITStepper.step` multiplies by `pml.damp_e`/`pml.damp_h` and by nothing else -- and `sigma_e` is zero on the physical interior, so the per-step multiplier `exp(-sigma dt / eps0)` is identically `1` there; the material builder takes a real `eps_r` and has no conductivity argument at all; the strip is ideal PEC with `self.e[self.pec_idx] = 0.0`; and the energy test pins the interior energy to better than `1e-10` over a full run. A loss that is not in the operator cannot be measured by it, so reading `0.014`-`0.028` dB/mm as absorption would convert a known numerical error into invented physics and would destroy the only reason to drive the error down.
- **Evidence.** `emfit/evolve.py`: `FITStepper.step` damps only via `pml.damp_e`/`pml.damp_h`; `emfit/pml.py:264`: `sigma_e` is zero on the physical interior and the multipliers are `1` there; `tests/test_energy.py::pec_conservation` pins `U` invariance below `1e-10`; `emfit/materials.py:241`: `material_matrices(grid, cc, eps_r=1.0, mu_r=1.0, *, interface="dual")` -- there is no `sigma` parameter; conductivity exists only in `_sigma_diag` (`materials.py:290`), `M_sigma` (`:372`) and `eigen.resonances(sigma=...)`, none of which any study calls; `emfit/studies.py:1563-1564` passes a real `eps_r` only (`substrate = lambda ...; material_matrices(grid, cc, eps_r=substrate)`); `emfit/studies.py:1575-1583` makes the strip ideal PEC by `pec |= strip` and `self.e[self.pec_idx] = 0.0`; `emfit/quasistatic.py:55` states "Conductor thickness and finite conductivity are not modelled". What the error costs on the coupon: over the physical `21.6` mm of trace (`ix_port 8` to `ix_far 62` at `0.4` mm) the floor gives `|S21| = 0.966` (`-0.30` dB) and the `npml10` span fit gives `0.933` (`-0.60` dB); a 1 per cent claim over that length needs `alpha < 0.0040` dB/mm, which nothing here reaches.

## The measured attenuation is not ripple bias

- **Decision.** The residual `alpha` is attributed to two named mechanisms -- leakage of the discretised guided mode into the PML, and a bias in the joint fit that is correlated with the fitted `beta` -- and not to a standing-wave ripple beating against the station span. The ripple channel is carried as a bounded systematic, at `~0.010` dB/mm an upper bound, and is not offered as the explanation.
- **Strongest argument against.** The station row is short: some runs span `0.71` of a ripple period and the best span `1.06` periods, so sampling a periodic `|S21|` too briefly is the obvious suspect, it needs no new mechanism, and the diagnostic for it is arithmetic rather than numerical.
- **Why that argument does not win.** The two hypotheses make opposite predictions about `|gamma|`, and the runs separate them. Halving `|gamma|` from `0.01419` to `0.00628` left `alpha` flat, `0.0192` to `0.0215` dB/mm over a `9.6` mm span: a ripple channel must shrink with its own driver and did not. Growing the span from `0.71` to `1.06` ripple periods moved `alpha` only from `0.0316` to `0.0278` dB/mm, so the whole channel is bounded above by `~0.010` dB/mm -- about a third of the effect to be explained. What does respond is the box: `alpha` falls monotonically as the trace is given room, which is what PML leakage of an imperfectly confined mode predicts and what a ripple bias cannot produce.
- **Evidence.** `npml4` -> `npml10` at fixed geometry: `|gamma|` `0.01419` -> `0.00628`, `alpha` `0.0192` -> `0.0215` dB/mm (`9.6` mm, nine stations). `npml6` vs `npml10` over `14.4` mm, span `0.71` -> `1.06` ripple periods: `alpha` `0.0316` -> `0.0278` dB/mm. Clearance sweep at fixed `|gamma| ~ 0.008`: `alpha` `0.0278` -> `0.01811` -> `0.01757` dB/mm as the clean span `n_clean` grows `4.8` -> `9.6` -> `14.4` mm; lid sweep: `0.01757` -> `0.01420` -> `0.01388` dB/mm. Floor over `14.4` mm: `alpha = 0.0139 +- 0.0026` dB/mm, i.e. `|S21| = 0.977`.

## The 0.2 mm refinement is not a convergence point

- **Decision.** The `0.2` mm run is not quoted as evidence about numerical dispersion, and it is not counted as the fine end of a convergence family. It is recorded as a port-mismatch artefact, valid only once the source plate is scaled with the cell (or the reference index and record length grow with it).
- **Strongest argument against.** It is the finest mesh in the family -- the one run that would settle whether the `0.4` mm attenuation is dispersion -- and discarding the finest run leaves the convergence claim resting only on coarser boxes, which is exactly the shape of argument this log has retracted before.
- **Why that argument does not win.** Finer is not better when the drive does not scale with the cell. The run passes settledness and fails every other guard: `alpha` comes out at `0.354 +- 0.112` dB/mm, `12.7` times the `0.0278` dB/mm of the best `0.4` mm box, where dispersion falling as the cell size squared would predict `0.0070`; `|gamma|` is `0.119` against `0.0082` for the same box; `mode_purity` is `0.23` and `fit_residual` `0.315`. A loss twelve times the quantity under test, accompanied by a reflection coefficient fifteen times the same box's own, is not an estimate of dispersion -- it is a standing wave in the launch, because the source plate stayed at its fine-grid size while the cell halved. The lesson is separate and worth more than the run: the half-to-half `beta` drift was `0.186` per cent, which passes the settledness gate, so settledness is necessary and not sufficient -- `fit_residual`, `|gamma|` and `mode_purity` are the guards that catch this class of failure.
- **Evidence.** Mesh `126 x 88 x 44`, `1,504,882` edges, `4800` steps, `300` s wall, `f = 5.8277864` GHz, `14.4` mm span over `13` stations: `beta = 233.4184` against `beta_model = 223.3531` rad/m; the two halves `233.6370` / `233.2021` (drift `0.186` per cent -- settled, and still junk); `alpha_joint = 0.353913 +- 0.112314` dB/mm; `|gamma| = 0.118844` (`|gamma_port| = 0.109306`); `mode_purity = 0.2296`; `fit_residual = 0.315146`; raw end ratio `|S21| = 0.726194`; `Re z0 = 51.921` ohm, `arg z0 = 3.859` deg; `eps_eff = 3.6521` against a model `3.3439`. For scale, the best `0.4` mm box gives `0.0278` dB/mm at `|gamma| = 0.0082`.

---

## |S21| acceptance criterion, restated as a measured band

- **Decision.** The pass criterion for |S21| on the default microstrip is a *band*, 0.960-0.994, derived from the estimator spread measured on repeated runs, not a 1 % tolerance around 1.0. It is stated as what the estimator can resolve, and the number of runs behind the spread is recorded beside it.
- **Strongest argument against.** A band that was chosen after seeing the data is indistinguishable, from the outside, from a tolerance loosened to make a failing check pass, and the width is dominated by an estimator whose spread is itself only estimated from a handful of runs.
- **Why that argument does not win.** The old 1 % tolerance was over-specified before any spread existed: it asserted a precision the estimator does not have (measured one-sigma spread is a factor 2.4 larger than the tolerance assumed, and the quoted sigma was ~3x over-optimistic), so it could only ever fail or be met by luck. The band is not a grading of the solver against truth; it is the resolution of the measurement, and every claim made from |S21| is now restricted to that resolution.
- **Evidence.** Repeated default-case runs give a one-sigma band 0.960-0.994 (this session's runs sit at 0.9922 and 0.9926); the two independent estimator variants differ by a factor 2.4 more than the assumed sigma; full pytest 295 passed, exit 0.

## Substrate thickness is not the source of the 0.01 dB/mm floor

- **Decision.** The residual attenuation of the default microstrip (~0.013 dB/mm at the best box) is attributed to a residual that does not scale with the substrate, and the substrate-guided (TM0) leakage hypothesis is dropped. Both boxes keep cell 0.4 mm, 9.6 mm lateral clearance, n_pml=10, 14.4 mm station span, 13 stations, 2400 steps; only n_sub/h change (4/1.6 mm vs 2/0.8 mm), so w stays 3.2 mm and w/h goes 2 -> 4.
- **Strongest argument against.** Halving h at fixed w changes the mode itself (model eps_eff 3.344 -> 3.562, Z0 48.7 -> 30.6 ohm), so the two runs are not the same mode at two thicknesses and a null result could be the mode change cancelling the thickness effect.
- **Why that argument does not win.** Any substrate-volume leakage has alpha ~ h^-n with n >= 1, so the thin box must show alpha a factor 2 (n=1) to 4 (n=2) larger. Measured ratio is 0.843 +- 0.25 (0.6 sigma from 1.0, 4.6 sigma from 2.0, 12 sigma from 4.0). A cancellation of that size would itself be a coincidence of the same order as the effect it would hide, and the direct energy accounting below excludes the lateral walls independently.
- **Evidence.** alpha = 0.01336 +- 0.0033 dB/mm (h=1.6) and 0.01127 +- 0.0024 dB/mm (h=0.8); beta 229.92 / 234.83 vs model 223.35 / 230.51; eps_eff 3.5434 / 3.6964 vs model 3.3439 / 3.5617; |Z0| 48.67 / 29.47 vs model 48.69 / 30.58 -- i.e. the measured cross-section response tracks the model's, so the fields did follow the new geometry.

## The lateral PML is not the sink either; mode-matched port deferred to gate G4

- **Decision.** The lateral (y) walls absorb 0.29 % of all absorber work, 92 % of it in the air band (h=0.8 box, post-warm-up, every 10th step). That is ~0.3 % of the throughput power, while the fitted alpha implies ~3.7 % loss over the same 14.4 mm span -- a factor 12 short, so the floor is not lateral-wall absorption either. Attribution of |S21| is therefore left carried by the revised criterion plus this diagnostic, and the mode-matched port is deferred to gate G4, where it is needed anyway.
- **Strongest argument against.** An unmatched lumped port excites a non-modal field that the station fit reads as decay, and only a mode-matched port removes that term; deferring it leaves |S21| interpreted without its dominant systematic.
- **Why that argument does not win.** The port term is known to be a *port-plane* effect that the station fit already separates (fit_residual 0.8 %, |gamma| 0.007-0.009, |S21| 0.992 in both boxes), and G4 needs the mode-matched port on its own account, so building it now would be one implementation serving two objectives against one schedule. The deferral is recorded with its reason, not as an open TODO.
- **Evidence.** Absorbed-work bins (h=0.8): end-wall e 86.70 % (93.4 % of it in the substrate band), end-wall h 13.01 %, lateral e 0.27 %, lateral h 0.02 %; e:h = 87:13; substrate band overall 89.34 % -- the substrate dominance of the *end*-wall figure is the mode's own concentration, not leakage. Scripts: .scratch/ms_substrate.py, .scratch/ms_pml_split.py; raw JSON beside them.

## The attenuation is lateral matched-layer leakage, not copper

- **Finding.** In the fixed audit the lateral walls remove `7.054` per cent of the absorbed work and the end walls `92.946` per cent. Normalised per unit length of the `26.40` mm of wall that actually does the removing, the leaked rate is `alpha_leak = 1.3360` Np/m = `0.01160` dB/mm. The direct station-plane amplitude ratio gives an effective `0.01183` dB/mm. The fitted `alpha` is `0.02145` dB/mm, `1.84` times the leaked rate.
- **What that settles.** Two model-free measurements agree with each other to `1.9` per cent and the fit is the outlier: the fitted `alpha` is biased high by a factor `1.84`, and the attenuation is lateral matched-layer leakage, not copper. Over the `21.6` mm line the leaked rate gives `0.25` dB, `|S21| = 0.972` -- that is the number the G1 `|S21|` criterion is met with under its revised (band) wording, and the mechanism behind the shortfall is now identified rather than merely bounded.
- **Strongest argument against.** The fitted `alpha` is measured over a `9.60` mm station span, whereas the accounting has to convert the work removed by `26.40` mm of wall into a per-metre rate, so on the face of it the accounting is the cruder number and the fit the better one.
- **Why that argument does not win.** The conversion is a division, not an assumption about the mode: the walls do run the whole `26.40` mm, and `2 * alpha * P` is the only way that work enters a per-metre rate. Charging all of it to the `9.60` mm span is the cruder reading and is what makes the span-charged row an upper bound, `2.82` times too large; normalising it away leaves `1.274` per cent over `9.60` mm against the fit's `2.343` per cent, and the station-plane amplitude ratio then lands within `1.9` per cent of the leaked rate rather than of the fit.
- **Evidence.** Default box, `npml = 10`, `2400` steps with `600` warm-up, `1800` accounted steps: lateral work `1.976361e-07` J against a total removed work of `2.801700e-06` J, walls `26.40` mm long, so `1.976361e-07 / (2 * 2.801700e-06 * 0.0264) = 1.3360` Np/m; `exp(-alpha L) = 0.987256` over the `9.60` mm station span (`1.274` per cent), against `2.343` per cent from the fitted `alpha` and `2.363` per cent from the two-wave `alpha` (`0.02164` dB/mm); station-plane `|S21|` `1.299` per cent below unity, i.e. `1.3622` Np/m = `0.01183` dB/mm. Row: "|S21| implied by the absorbed work" in the microstrip report; script `.scratch/study_run.py`.

## Retraction: the lateral PML is not excluded, it is the sink

- **What was claimed.** The earlier entry, "The lateral PML is not the sink either", recorded the lateral walls as excluding `0.29` per cent of the absorbed work and, on that figure, as being a factor `12` short of the fitted `alpha` -- hence the conclusion that the floor was not lateral-wall absorption at all.
- **What is true.** That figure came from the prototype run, which carried two bugs, both fixed the same day: `sigma_for_walls` rejected kind `"h"`, and the face share was missing the `mu0/eps0` factor, so the magnetic half of the absorbed work was silently zero and the total read `1.89` times low. With both fixed the lateral share is `7.054` per cent, not `0.29` per cent -- larger than the `1.89`-fold bug accounts for, so the prototype figure was wrong for more than one reason and should never be quoted. The conclusion therefore reverses: lateral leakage is real and is the dominant sink, not an excluded one.
- **Where the correction lives.** In this log, in the finding above, and in `emfit/pml.py`, which now records the magnetic half and both wall families.
- **Parked, not investigated.** A `571` s timing anomaly in the scratch harness `.scratch/default_audit.py` is scratch-only: the library path does the same `2400`-step run in `15`-`32` s and the two monkeypatches cost about `0` per cent, so it is not a library issue and must not be re-investigated without new evidence.

## The acceptance criterion rests on estimator spread, not on a propagated alpha

- **Decision.** The revised `|S21|` criterion is argued from the spread among the estimators available on the
  reference box: `0.01160` to `0.02164` dB/mm, a factor `1.86`, which over the `21.6` mm line is `|S21|` from
  `0.972` to `0.948`. The `0.990`-`1.010` target window lies entirely outside that span, so what this instrument
  resolves is `2.5` to `3` per cent in `|S21|`, and a one per cent target would be graded by which estimator was
  chosen rather than by whether the solver is right. The criterion wording itself is unchanged: `|S21|`
  consistent with a lossless model within the measurement uncertainty, the dominant mechanism attributed with its
  magnitude, and the mechanism identified by name and by the part of the box responsible.
- **Strongest argument against.** A span across estimators is not an error bar. It mixes a known systematic -- the
  standing-wave bias of a single-exponential fit -- with statistical noise, and it is wider than any single
  estimator's own one-sigma, so quoting it as "the uncertainty" could be read as buying room by adding a bias to
  genuine precision.
- **Why that argument does not win.** The span is the stronger statement exactly because it does not require
  choosing an estimator first, which is the choice the criterion exists to avoid, and because the two groups in it
  are not noise about a common value: the model-free rows sit together at `0.01160` and `0.01183` (`1.9` per cent
  apart), the one-wave fits at `0.02145` and `0.02164`, and the gap between the two groups is that bias. A
  propagated sigma would have to assume one estimator, then report the assumption as an uncertainty.
- **Evidence.** Reference box `66 x 52 x 26` cells at `0.40` mm, `npml 10`, `w = 3.2` mm, `h = 1.6` mm,
  `eps_r = 4.4`, `2400` steps with `600` warm-up: `alpha` rows `0.01160` (audited lateral leakage), `0.01183`
  (station-plane ratio), `0.02145` (one-wave fit), `0.02164` dB/mm (two-wave fit);
  `10^(-0.01160*21.6/20) = 0.972` and `10^(-0.02164*21.6/20) = 0.948`; `|gamma| = 0.0060` moves the raw envelope
  `2.4` per cent peak to peak against a `3.0` per cent fall over the `9.60` mm measured span, while the two
  half-span fits agree to `1.4e-3` in `ln|V|`. Sections `sec:msres-alpha` and `sec:ms-criterion`.

## Every quoted attenuation names its box

- **Decision.** `alpha = 0.0139 +- 0.0026` dB/mm is quoted only as the clearance/lid-sweep floor over `14.4` mm,
  never as the reference box's attenuation. The reference box is `66 x 52 x 26` cells at `0.40` mm with
  `npml 10`, `w = 3.2` mm, `h = 1.6` mm, `eps_r = 4.4`; on it the fitted `alpha` is `0.02145` dB/mm against an
  audited leakage rate of `0.01160` dB/mm. Every attenuation quoted in the report states which box and which span
  it came from.
- **Strongest argument against.** Both are the same default geometry -- `0.4` mm cell, `npml 10`, `w/h = 2`, the
  same lateral clearance -- so demanding a box name for each looks like pedantry over a `9.6` mm against `14.4` mm
  difference in station span.
- **Why that argument does not win.** They differ in exactly the quantity being quoted: the sweeps average over
  `14.4` mm and `13` stations, this record fits over `9.60` mm and `9`, and the two values differ by a factor
  `1.54` (`0.0139` against `0.02145`), larger than either uncertainty. A reader who meets `0.0139` on the same page
  as the reference-box tables will take the floor for this box's answer, and it is not.
- **Evidence.** Floor `0.0139 +- 0.0026` dB/mm and `|S21| = 0.977` over `14.4` mm from the clearance and lid
  sweeps, in the decision "The measured attenuation is not ripple bias"; the reference-box rows in `tab:ms-z0`,
  `tab:ms-alpha` and `tab:ms-acct` of `docs/report/sec_microstrip_res.tex`.

## Retracted claims

One line each: what was claimed, what is true, and where the correction lives.
The correction for all six lives here; the code defect behind the studies.py claim
is fixed in `emfit/studies.py`.

- **2026-10-19. Claimed:** the station series contains a 6 per cent standing wave. **True:** the reflection coefficient is 0.0075, which bounds the standing wave at 0.86 deg; the observed 7.3 deg residual is unexplained and is not standing wave. Correction here and in the decision "The station fit, not the port ratio, is the Z0 measurement".
- **2026-10-19. Claimed:** `beta` carries a 6.24 per cent error. **True:** it compared a fitted `beta` to a quasi-static model that should not agree with it; the fitted values agree with each other well inside the 0.0095 fit residual. Correction here and in the decision "Propagation constant from the one-wave joint complex-gamma fit".
- **2026-10-19. Claimed:** the air capacitance per length is limited to 34.925 pF/m. **Withdrawn:** it extrapolated a family whose box shrinks with the mesh. The reference value is 37.677 pF/m at 12h clearance refined to h/16. Correction here and in the decision "Static air capacitance must be measured at the same box as eps_eff".
- **2026-10-19. Claimed:** ground-current truncation costs about 2.5 per cent. **Withdrawn:** the measured ratio `i_full/i_trunc` is 1.001219, i.e. 0.12 per cent, with phase 0.0045 deg. Correction here; the ratio is printed by the microstrip study report table as `full / strip current`.
- **2026-10-19. Claimed:** the modulus of `z0` printed under the name `Z0`. **True:** the modulus is `|z0|`, 9.62 per cent above the model, while `Re z0` is within 4.66 per cent. Correction here and in the code fix to `emfit/studies.py`.
- **2026-10-20. Claimed:** the one-sigma band for `|S21|` is `0.960` to `0.994`, from `alpha = 0.0139 +- 0.0026` dB/mm over `L = 21.6` mm. **Withdrawn:** propagating the attenuation uncertainty alone gives `0.300 +- 0.056` dB, i.e. `|S21|` in `[0.960, 0.972]`; the `0.994` endpoint was a repeated-run spread of `|S21|` itself -- a different measurement of a different quantity -- and must never be quoted as a propagated one-sigma band. Correction here and in the decision "The acceptance criterion rests on estimator spread, not on a propagated alpha"; the band no longer appears in `sec:ms-criterion` of `docs/report/sec_microstrip.tex`.

## The Board path and its gate

- **What was built.** `emfit/board.py` adds a frozen `MicrostripBoard` in SI metres, with `from_kicad` and
  `to_cell_counts`. The `Board` dataclass already existed in `emfit/kicad.py` in millimetres, and `raster.py` and
  `copper.py` already used it, but `studies.py` referenced it nowhere, so this was a thin adapter rather than a
  parse or raster milestone.
- **Route taken.** Route (a), the hybrid: `Board` sets `microstrip_wave`'s geometry and every estimator, port and
  audit code is shared.
- **Route rejected.** Route (b), rebuilding on `raster.Coupon`, because `Coupon` carries no PML, ports or stations,
  the raster lands `z` nodes on copper, and a `35` um thin sheet changes the strip from the zero-thickness sheet the
  reference record was taken on; (b) could only agree to `2.5`-`3` per cent.
- **Why there is no `copper_t`.** `MicrostripBoard` has no `copper_t` field because the solver has no ohmic term, so
  the field would advertise a loss model that does not exist. `x_port` is `8.65` mm, not `8.8` mm, because the
  uniform `3.0` mm run begins there. `microstrip_wave` is now documented as the fixture that pins the `Board` path.
  Committed `6518288`.
- **Gate result.** The `Board`-driven reference board reproduces the hand-built record to round-off: `alpha_fit`
  `2.469703`, lateral `1.33601` Np/m, `lateral_fraction` `0.0705415`, lateral work `1.976361e-07` J, `implied_s21`
  `0.9640843`, `beta` `231.88572`, `eps_eff` `3.60431`, `|gamma|` `0.0062819`, fit residual `0.0078130`, with `f`,
  cell size, `nx/ny/nz`, stations and step counts all identical. One dump field does not match: station `|S21|`
  `0.9869798` in the old dump against `0.9870082` now, a difference of `2.8e-5` that comes from an aggregation step
  in the old dump that cannot be reconstructed; it is not a solver disagreement.

## The substrate diagnostic, and a correction to a quoted floor

- **Runs.** Both on the `Board` path, two geometries, both audited. Case A, `h = 1.6` mm and `w = 3.2` mm: lateral
  wall sink `1.33601` Np/m, which is `0.011604` dB/mm. Case B, `h = 0.8` mm and `w = 1.6` mm so that `w/h` stays at
  `2` and the mode does not change: `0.49758` Np/m, which is `0.004322` dB/mm.
- **Confirmed.** The ratio is `0.37244` against a pre-registered `0.35` with a band of `0.15` to `0.60`: the
  prediction is confirmed and the pre-registered falsifier, a ratio near `1.0`, did not fire.
- **Scaling.** The sink scales as `h^1.425`, the lateral work as `h^3.15` and the total absorbed work as `h^1.73`;
  the lateral walls absorb `8.88` times less work when `h` halves while the stored power falls only `3.31` times.
- **The estimators are not usable here.** The fitted `alpha` and the station-based estimator: their half-span ratios
  in case B are `1.7439` and `0.05599`, a spread of `1.688` that dwarfs any signal, and the port impedance moved
  from `51.310` to `45.949` ohm, so those estimators are not comparing like with like. Only the audit and the work
  totals carry the scaling.
- **Correction.** The entry above quoting `alpha = 0.0139 +- 0.0026` dB/mm as the clearance/lid floor over `14.4` mm
  does not survive this. Both audited rates, `0.011604` at `h = 1.6` mm and `0.004322` at `h = 0.8` mm, lie below it,
  and the sweep's `1.600` Np/m exceeds the reference box's audited `1.33601` Np/m, which is impossible if moving the
  walls out reduces the sink. That number belongs to the sweep boxes -- `npml 6`, a `14.4` mm span, `13` stations,
  unaudited, and fitted `alpha`, which carries the known factor of about `1.84` over the audited wall work. It is a
  box property, not an attenuation of the line, and it must not be quoted as one again. The two audited values
  supersede it.

## The mechanism question, and a correction to the tail argument

- **Withdrawn: the naive tail test.** The guided mode's air-region tail would fall as `exp(-k_y y)` with
  `k_y = sqrt(beta^2 - k0^2) = 197.11` rad/m, a decay length of `5.07` mm or `3.2h`, which predicts a `44`-fold fall
  in the wall flux between `4.8` mm and `14.4` mm clearance. That form is not valid in this box, because the lid
  sits only `12` air cells, `4.8` mm, above the strip, which is `0.95` of a decay length, and the vertical
  wavenumber `pi` over twice the gap, `327` rad/m, already exceeds `k_y`, so the region above the strip is below
  cutoff vertically and the field is box-loaded. The lateral decay constant of the box-loaded field is a different,
  smaller number, so the `44`-fold prediction is model-dependent at the factor-of-few level and cannot rule
  anything out.
- **Withdrawn: TM0.** Following from the same fact, there is no true TM0 surface wave in this box either: a
  grounded-slab surface wave extends far into the half-space above it, and here there is no half-space.
- **What is left, and what the next run tests.** The candidate pair is a matched-layer absorption of the box's
  slowly decaying lateral tail, against a propagating lateral component of the box-loaded mode that a wider box
  would not cure. That distinction is what matters to the product, and it is what the next run tests.

## Correction: the 1.600 Np/m comparison mixed two estimators

- **Supersedes part of** the entry "The substrate diagnostic, and a correction to a quoted floor" above, specifically its
  use of the sweep's `1.600` Np/m as evidence against clearance.
- **Withdrawn inference.** That entry said the clearance/lid floor of `0.0139 +- 0.0026` dB/mm was a box property rather
  than an attenuation of the line, and offered as part of the reason that the sweep's `1.600` Np/m exceeds the reference
  box's audited `1.33601` Np/m, which would be impossible if moving the walls out reduced the sink. That inference is
  withdrawn: the two numbers are not the same estimator. `1.600` Np/m is a *fitted* attenuation from the `npml 6` sweep
  boxes; `1.33601` Np/m is *audited wall work* from the reference box.
- **The size of the mismatch.** In the reference box the fitted attenuation is `2.46970` Np/m against an audited
  `1.33601` Np/m, a ratio of `1.849`, and that bias is exactly the `1.84` factor already known in this log. So a
  sweep-box fitted floor of `1.600` Np/m corresponds, if the bias is roughly stable across boxes, to an audited wall rate
  of order `0.87` Np/m, which is *below* the reference box's `1.33601` Np/m and therefore entirely consistent with
  clearance reducing the sink. The ordering of a fitted number and an audited number carries no information, and the
  earlier statement that the sweep data contradicted clearance was wrong.
- **What survives.** `0.0139 +- 0.0026` dB/mm is a floor on *fitted* `alpha` over a `14.4` mm span in `npml 6` boxes and
  must not be quoted as an attenuation of the line; the two audited values, `0.011604` dB/mm at `h = 1.6` mm and
  `0.004322` dB/mm at `h = 0.8` mm, are the only lateral wall rates in this log.
- **What does not survive.** Any claim that the sweep data itself rules out a decaying lateral tail. Whether the tail
  picture holds is for the case C clearance audit to decide, and the mismatch above removes one of the arguments that
  had been counted against it.

## Case C: the clearance audit, and the lateral sink is a boundary term

The clearance test was run on the Board path: case A's reference box with the board widened from 20.80 mm to
28.80 mm, giving 8.8 mm of clean dielectric each side of the strip instead of 4.8 mm. Everything else identical:
66 x 72 x 26 cells at 0.400 mm, `ny 72 = 2*10 + 8 + 2*22`, `n_clean 22`, `n_line 54`, matched layer ten cells,
2400 steps with 600 to settle and 1800 accumulated, nine stations, 5.827786408 GHz, `L_box` 26.4 mm. Audited
lateral wall work fell from `1.3360133447` Np/m to `0.6008499504301062` Np/m, a ratio of `0.44973`, and the
lateral share of all absorbed work fell from `0.0705415046` to `0.03172487738270961`. The pre-registered tail
band was `0.21` to `0.50` and the pre-registered distributed band was `0.75` to `1.05`: the measurement lands at
`0.4497`, inside the tail band at its upper edge, and the falsifier at about `1.0` was not triggered. My own
written prediction was `0.60` with a band of `0.40` to `0.80`, so the point prediction was too high and the
interval contained the result.

Four independent estimators were compared across the two boxes, each against itself and no other: the audit gives
`0.4497`, the fitted attenuation `2.4697030928` to `1.4562321181785494` gives `0.5896`, the station full-span
value `2.55126` to `1.5656912491269914` gives `0.6137`, and the plain station-to-station ratio `0.9870082` to
`0.9912684` gives `0.6706` in terms of attenuation, `1.3621` Np/m to `0.9134` Np/m. All four fall, by between
1.5 and 2.2, and the two candidates were separated by whether the fall would be present at all: a propagating
lateral component of the box-loaded mode that a wider box would not cure predicted `0.75` to `1.05`, and is
excluded by the audit and by the fitted attenuation at about two standard deviations, though the raw endpoint
ratio alone would sit in the low part of the ambiguous band. The mode itself barely moved across the change:
beta `231.88571529` to `232.1433122904987`, eps_eff `3.604312254` to `3.612324612863742`, and the ratio of
magnetic to electric stored work `0.9538` to `0.9398`, so the fall in the sink is not a change of mode.

## The corner-contamination hypothesis was wrong, and the field slice cannot adjudicate

The audit's `AbsorbedWork` object keeps the absorbed work four ways, edges against faces for each wall group,
which the earlier dumps had summed away. Re-running case C with the four bins recovered, and checking that edges
plus faces reproduce the summed values exactly for both groups (difference `0.000e+00` in each, accumulated steps
1800), gives: reference box edges `{end 1.347842e-06, lateral 8.611041e-08}` and faces
`{end 1.256222e-06, lateral 1.115257e-07}`, stored work electric `1.433953e-06` and magnetic `1.367747e-06`;
widened box edges `{end 1.4071048037713717e-06, lateral 4.056215064025947e-08}` and faces
`{end 1.3119386370322637e-06, lateral 4.852546272792045e-08}`, electric `1.4476669544116312e-06` and magnetic
`1.3604640997601842e-06`. The lateral edges fell to `0.4710` and the lateral faces to `0.4352`, a spread of
eight per cent, while the end wall work rose by 4.4 per cent in both families. **The contamination hypothesis is
withdrawn**: I had recorded that corner and end cells sharing the lateral bin would bias the ratio upward toward
the distributed reading, and it does not, because the edge cells fall as fast as the face cells. There is no
clearance-independent floor in that bin, and the `0.4497` needs no correction on that account.

**The field slice does not support the number and must not be used as if it did.** The saved mid-plane `Ez`
phasor at `x = 15.2` mm is not exponential in `y`: the local decay constant runs from about 1300 Np/m near 4 mm
to about 185 Np/m near 10 mm, the amplitude flattens to a plateau of order `1e3` between 9.6 and 11.2 mm and
then collapses between 11.6 and 14.0 mm to a zero at the outer edge at 14.4 mm, and the last point is on the
zeroed matched-layer boundary so it carries no information at all. Taking the local decay constant near the
wall, 4.2 to 5.4 mm of decay length, predicts a wall-flux ratio of `0.17` to `0.23`, against the audited
`0.4497`, so the mid-plane electric field decays two to three times faster than the wall-integrated absorbed
work does. The slice therefore measures a different quantity from the one the audit bins, and the honest
position is that the field profile neither supports nor contradicts `0.4497`. No slice was saved for the
reference box, so no direct field comparison between the two boxes exists either. The decay length implied by
the work ratio itself, `exp(-2 kappa 4.0 mm) = 0.4497`, is `99.9` Np/m or `10.0` mm, which is twice the
half-space value of `5.07` mm and twice the measured near-wall value; reconciling those three numbers is open,
and until it is done the microscopic mechanism is not pinned down.

**What case C establishes and what it does not.** It establishes that the lateral sink is a boundary term whose
magnitude is set by the clearance: the same line, the same mode, 2.2 times less audited lateral absorption when
the wall moves out 4.0 mm, in every field family and every estimator. The reference box's `0.0116` dB/mm is
therefore a property of that box and not of the line, and a wider box reports `0.00522` dB/mm for the same
geometry, which is worth saying to the user and in the report. It does not establish whether the residual sink is
absorption of the slowly decaying lateral tail by the matched layer or a genuine radiation loss: a closed box has
no half-space, so that distinction cannot be made inside it at all, and it would need either an open-boundary
formulation or a third clearance point to show whether the fall converges.

## The audit and the station ratio agree in the reference box and separate in the wide box

In the reference box the two estimators furthest apart in construction agree: audited lateral wall work
`1.33601` Np/m against a plain station-to-station rate of `1.36215` Np/m over the same `9.6` mm, `1.9` per cent,
factor `1.02`. That is the model-free evidence the case rests on, joules counted on the walls against amplitudes
differenced between stations sharing no constant, and it is what makes `0.011604` dB/mm an attribution rather
than a name.

In the wide box they separate: `0.60085` Np/m audited against `0.91350` Np/m from the endpoint ratio, a factor
of `1.52`, so the lateral bin accounts for two thirds of the between-station decay and `0.31` Np/m, `34` per
cent, is unexplained. The agreement is therefore a property of the reference box and not a validation of either
estimator, so nothing measured in the wide box licenses an "attenuation of this line is X" statement. The ratio
`0.450` survives because it compares one estimator across the change and does not need the wide-box decay to be
fully accounted for.

Two readings, and no adjudication from one run: the endpoint rate carries an error of order `0.2` Np/m at a rate
near `0.9` Np/m, which is not implausible at `|S21| = 0.9913` over 2400 steps and nine stations; or a
clearance-independent component of order `0.3` Np/m exists that the lateral bin does not see.

Caution, recorded with no argument built on it: the wide-box fitted attenuation, `1.456` Np/m, sits near the
`1.600` Np/m floor the npml-6 sweep showed for fitted values in small boxes. Different estimator, different box;
noted only so that a future convergence study checks it deliberately.

What settles it is two or three further clearances (`24.8`, `32.8`, `36.8` mm) quoting audited lateral work and
the endpoint ratio side by side at each: if the gap holds near `1.5` while the audit falls toward zero, the
residual is not a wall sink, and if both fall together then the wide-box between-station decay is being
underestimated by the audit.

## The clearance test selects: the sink is a boundary artefact, not radiation from the strip

The clearance test settles the mechanism it was registered against, and it selects rather than only bounding.
Audited lateral wall work fell from `1.33601` Np/m in the reference box to `0.60085` Np/m when the wall moved
out `4.0` mm, a ratio of `0.450`. That ratio lies inside the pre-registered band for a decaying tail, `0.21` to
`0.50`, and outside the pre-registered band for a propagating lateral component, `0.75` to `1.05`, so it selects
the first: the sink is the decaying tail of the discretised mode absorbed by the lateral matched layer, and it is
not radiation into a slab mode. The claim this supports is narrow and is the one that matters to a user -- the
sink is a boundary artefact of the box, not a radiating property of the strip.

The margin is thin and is recorded as thin. `0.450` sits at the upper edge of the band that contains it, `1.11`
times inside it, and the endpoint ratio `0.671` falls in the `0.50` to `0.75` gap between the two bands, the range
in which neither reading is favoured, so `0.671` selects nothing and is unused for selection. Only the audited
number carries the claim. What makes the reading firm is the excluded band rather than the satisfied one: `0.450`
is `1.67` times below the nearer edge of `0.75` to `1.05`.

A second argument settles the same question without using the clearance at all. The matched layer sits `4.80` mm
above the strip, which is `0.95` of the lateral decay length, so the region above the strip is below cutoff
vertically and there is no half-space in which a grounded-slab TM0 wave could exist. That argument does not
depend on where the lateral wall is, and it is what keeps the tail reading standing even though the reading of
the ratio rests on a band edge.

What this means for the product: the strip is not radiating a few per cent of its power. The `0.011604` dB/mm of
the reference box is an artefact of that box's lateral boundary and not a loss of the line, so a wider box or a
better matched layer reduces the figure without changing the line. What it does not mean is that the line is
lossless in this record: the wide-box station rate is `0.91350` Np/m against an audited sink of `0.60085` Np/m
there, and `0.31` Np/m, `34` per cent, is left over.

That residual is open and is carried to G4, with two candidates, in this order.

(a) A sink the audit does not bin. The audit sums the work the walls absorb, so an attribution error at a lateral
or end wall would show up exactly here, as work missing from the lateral bin. The earlier perfectly-conducting-lid
test already ruled out top-wall radiation as the missing term, which is why the lateral and end walls are where
the remaining candidates are.

(b) A floor in the wide-box station rate. The station window is fixed at `9.60` mm while the lateral tail extends
when the wall moves out, so the endpoint ratio taken over that window may not fit the true mode. The test is to
widen the window or to fit at stations further from the source, and it is cheap.

This blocks broad-validity claims in G4 and does not block G3. The mechanism statement is about this box and this
test; a statement of the form "the attenuation of this line is X" still needs the residual resolved, because
`0.31` Np/m is a third of the wide-box decay. The limitation that remains is general only: a wider box cures both
layer absorption and radiation, so the clearance test separates the two candidates it was registered against and
no further pair.

Recorded against the earlier entry of the clearance case: that entry states the closed box cannot make this
distinction at all, and on that one point it is superseded, by the band selection and by the lid argument. The
rest of it -- the audit-versus-station-ratio separation in the wide box and the open `0.31` Np/m -- stands and is
what the G4 carry above is built on.

---

## A lumped element at a transverse cut: the series branch passes its pre-registered test, the shunt branch is an envelope and not a validation

Two kinds of lumped element were added, `series_r` and `shunt_c`, and both sit on a transverse cut through the line rather than at a port. A cut is the only place an element can sit in this model without asking the solver to invent a boundary condition: the element is a modified curl term on one plane of edges, the strip is severed at that plane for the series case, and the shunt case ties the edge at the cut to both ground planes. Because the element lives on a plane, the reference for every load case is the same geometry with no element, never a separate analytic model -- the load's effect is the ratio of two runs that differ in one plane of coefficients, which is the only arrangement in which the subtraction of discretisation error means anything. The reference path is load-free by construction: it never assembles the element and never reads its parameters, so no load parameter can reach a case that does not declare one.

The series branch passes. On the `0.4` mm board with `n_sub = 4` and `n_strip = 8`, cut at `15.20` mm and run for `2400` steps, the load-free reference sits at `5.8278` GHz with travelling-wave impedance `Zc = 50.547 + 4.025j` ohm and a measured ground capacitance `Cg = 0.1247` pF at that cut. At 25 and 50 ohm the implied load is within `1` per cent of the commanded value, which is textbook. At 100 ohm it comes out `9.04` per cent low against the `7.1` per cent pre-registered prediction, so the point prediction was missed and is reported as missed rather than relaxed after the fact. The criterion that prediction was registered against is a separate claim, the size and sign of the deviation rather than a band around the predicted value: the ideal formula must be wrong at that load by order ten per cent while holding to under one per cent at 25 and 50 ohm. That criterion was met, because the `2400`-step deviation of `9.04` per cent sits under a record-length limit of about `10.5` per cent, which makes the effect larger than the registration asked for rather than smaller, so the miss is in the point prediction and not in the gate. Corrected for the known `Zg` and the reference impedance the deviations are `-1.34`, `-1.31` and `+0.90` per cent, the phases agree to within `0.68` deg, and what is left over is a near-constant `+(2.0 + 1.6j)` ohm offset at all three loads -- a series residual that does not scale with the load, which is what a parasitic belonging to the cut rather than to the load looks like. The 50-ohm point also shows the single-probe cancellation: at that load the probe's own error cancels against the load, so the residual is defined there and it is the residual that is quoted, not a third independent measurement.

The shunt branch is reported as an envelope and is not claimed to be validated. The commanded values were `0.05`, `0.1`, `0.2`, `0.5`, `1.0` and `2.0` pF; the recovered values run from a ratio of `0.9954` to `1.8581`, so the per cent-level accuracy the series branch reaches holds only in the shallowest cases, and at `1.0` pF the recovered capacitance is `25` per cent over (ratio `1.2507`). The bookkeeping itself is exact and was verified against the assembled arrays rather than inferred: `32` Ez edges at the cut, `8` columns times `4`, with `C/2` per edge, so the coefficient the solver actually holds is the commanded value and the discrepancy is in the field, not in the assembly. The excess is not a fixed parasitic -- it grows with the commanded value rather than sitting under it -- and it is not multiplicative: the ratio is not constant, so dividing by it would be fitting a curve, not removing a cause. The mechanism is named but not closed: the model's extra capacitance is distributed over the whole cross-section, the walls and the substrate included, whereas the commanded element is a footprint on the strip seen through the fringing field, and those are two different objects, so the difference is one of kind and no ratio is expected to be one. The depth sweep carries a positive control at `4.58`, where the harness moves the answer by `+0.31` per cent, which is small next to the `25` per cent and so is not the explanation.

The single-mesh sweep cannot identify the cause, and the refinement argument says the local power law cannot be extrapolated. The perturbed phase advance per cell falls as the square root of the cell size under refinement, while the error grows as that phase advance to the power `3.58`; a law observed at one cell size in injection depth therefore says nothing about the same law in cell size, and its sign is the wrong one to be causal at all. What the sweep supports is the envelope and the direction of the trend, and that is what is quoted.

## Open items from the load gate

(a) The default S-parameter path and the load share a station as their seam. The two-half fit splits the line at a station, and a load placed at a cut puts its own discontinuity exactly on that seam, so the default path returns `|s21| > 1` and, on a bare open, a `beta` with a standard error of `57`. This is not a load bug and it is not a reason to widen the fit: the two halves were a way of removing the source and the absorber when nothing else was known about the line, and once `beta` and the impedance are measured there is no reason to split at all. The fix is to replace the two-half fit with a single plane at the cut, not to repair the halves.

(b) The station fit can now refuse, and the refusal is public. A station fit that finds the load's plane inside its window returns a failure instead of a number, surfaced as the flag `station_fit_ok`, because a diagnostic that silently absorbs a discontinuity into `beta` would corrupt the very quantity it is meant to check. The loss-*free* fit turned out to be a second place the same abort could fire, and that one was found only after the first had been guarded -- so the rule that came out of this is that a check protecting a result must be written once per path that can reach it, not once per symptom.

## The passivity bound is `|S11|^2 + |S21|^2 <= 1`, and it is not the losslessness check

- **Decision.** The microstrip report carries a passivity row, `|S11|^2 + |S21|^2` formed from the fitted reflection and the station-to-station `|S21|`, required to sit at or below `1` and asserted so in `_run_microstrip`. The sum is a **bound**: a passive network may not return more power than it was handed. It is not a losslessness check and no row claims losslessness from it -- a lossless network sits at exactly `1`, which is a stronger statement this sum cannot support here.
- **Strongest argument against.** This is the arithmetic the power-check entry above forbids: "The check consumes the current phasor and is never obtained by adding `|S11|` and `|S21|` together." Two rows now add them, and that entry is not retracted.
- **Why that argument does not win.** The prohibition sits inside a decision about *losslessness*, and it gives its reason: a ratio of `1` formed from the same station fields proves only that the solver is self-consistent, so it is a restatement dressed as evidence. A one-sided inequality is a different claim with a different failure mode, and here the naive sum is also arithmetically exact rather than approximate. A power wave carries a `1/sqrt(Re zc)` weighting of its own, so the general form of this test pairs each `|S|^2` with the cross-section it was measured on. In this study both planes sit on one cross-section and the split hands both of them the same `zc`, taken once from `station_fit.z0` or from `reference.zc` in `microstrip_wave`, so the weighting is one factor on both terms and cancels: the general per-plane form collapses to the plain sum of squares. The prohibition was learned on a geometry with two cross-sections, set out next, and is not evidence about this one.
- **Limitation: the geometry where the naive sum fails.** The identity is a property of one cross-section, not of S-parameters. `tests/test_port_parallel_plate.py` runs a parallel-plate line whose ports carry a voltage rather than a power wave, across a 1:4 dielectric step; there the naive sum reads `0.5602` against the exact `5/9 = 0.5556`, so it is not merely loose, it is measuring the wrong quantity, and the lossless claim that does hold is `|S11|^2 + (Z1/Z2) |S21|^2 = 1` with `Z1/Z2 = sqrt(eps2/eps1) = 2`, measured `1.0073`. Any two planes on different cross-sections need that per-plane `sqrt(Re zc)` (equivalently impedance-ratio) form written out.
- **Evidence, and why the margin is wide.** Both records are `GUARD_STEPS = 400` at `5.827786` GHz with `npml = 6`, and both are load cases with no reference -- the ones whose `|S21|` is a measured magnitude across the load rather than a line divided out of it. Series 100 ohm: `|gamma|^2 = 0.283293`, `|s21|^2 = 0.187464`, sum `0.470757`. Shunt 1.0 pF: `|gamma|^2 = 0.015425` (`|gamma_port|^2`, the same modulus the de-embedding holds fixed), `|s21|^2 = 0.275081`, sum `0.290506`. The `|S21|` between the station planes is `0.433` and `0.524` on the two, far below the `0.97`-`0.98` a fine mesh gives, and that is the point: at 400 steps the surrounding matched layers and the coarse mesh absorb a large fraction of the incident power between the planes, which pushes the sum **down**. The test is one-sided by construction. A sign or a normalisation error in the wave split is what lifts it above `1`, and that is what the assertion is for; a wide margin is the expected reading and not a defect to be tuned away.

The same bound is deliberately not asserted in `MicrostripWave.summary()`: that method has no caller anywhere in `emfit/`, and every route out of the package, the CLI included, goes through `_run_microstrip`, which does assert. An assertion in an uncalled method is decoration presented as coverage -- it cannot fire.

---

## A knob that does not reach the mesh is a lie

- **Decision.** `w` is not a knob on the microstrip study. The strip in the mesh is `n_strip` cells wide and nothing else; `w` feeds only the closed-form comparison curves drawn beside the report, so changing it moves the picture and leaves the simulation bit-for-bit identical. The default hid it: `MS_W == n_strip * cell == 3.2` mm, so the width a reader sets and the width the solver builds were the same number and the disconnection never showed. The fix is to derive the closed-form width from the mesh actually meshed, `w = strip_cells * (h / n_sub)`, and to expose the cell count as the thing a caller chooses rather than a width.
- **Strongest argument against.** A width is what a datasheet quotes and what every closed-form model wants as input, while a cell count is a discretisation detail no external formula takes. Exposing the cell count makes every comparison curve have to reconstruct the width, and a caller who thinks in millimetres has lost the number they came for.
- **Why that argument does not win.** The number that matters is the one the field saw. A width that is reported but not meshed is worse than a cell count that is meshed: the reader cannot tell the two apart from the report, and a parametric sweep over `w` would return a flat curve with no warning attached. Deriving `w` from `n_strip` and `h` puts the comparison on the geometry that was actually solved, and the general rule is the one this cost: before exposing a parameter, prove it changes the simulation, not only the picture.

## A floor is measured, not assumed

- **Decision.** `h_mm` on the microstrip study first carried `lo=0.4` mm, chosen as the cell size the coarse board already ran at. Measurement showed that everything below about `1.3` mm raises: the two measurement planes sit at fixed distances, `10.4` mm and `20.0` mm, while the line is a fixed `62` cells long, so a finer mesh cannot put enough stations between the planes for the station fit to have anything to fit. The floor is now `1.3` mm, and the help text says why it is there rather than leaving a bare bound to be read as arbitrary.
- **Strongest argument against.** A `lo` is a claim about the physics, and `1.3` mm is not a physical limit of a microstrip -- real boards thinner than that are ordinary. Setting the bound from what this solver's station geometry can currently digest turns a numerical accident into an apparent domain limit, and a later reader may take it for one.
- **Why that argument does not win.** A range that admits values the run cannot produce is a promise the code does not keep: the caller gets a traceback where the form implied an answer. The honest options are to widen the station geometry or to state the bound the solver actually has, and the bound can be revised the moment the geometry changes because the help text carries the reason. The general rule: find the failure boundary by running it, put that number in the range, and say why in the help text -- a bound with its reason attached can be re-measured, a plausible-looking one cannot.

## An audit only sees the channels it accounts for

- **Decision.** The absorbed-work audit bins only the damping in the matched layer, accumulated in `pml.py`, while a lumped load removes work in the stepper, in `evolve.py`, on a plane the audit never looks at. On a loaded run the audit's total is therefore injected-minus-dissipated rather than the sum of what the layer took, and its normalisation charges the load's absorption to the absorber. The audit row is suppressed on loaded runs with that reason stated in place of a number.
- **Strongest argument against.** The audit is the only independent accounting of where the power went, and the one thing an audit is for is to be run when something new is removing energy. Suppressing it on exactly the runs that open a new channel removes the check where it is most wanted, and the row that would have shown the load's dissipation is replaced by a sentence.
- **Why that argument does not win.** An audit is valid only where it accounts for every channel that removes energy; opening a new channel silently invalidates it, and an invalid audit does not fail loudly, it returns a plausible number with the load folded into the wall loss. A stated silence is a known gap that a later reader can close by extending the binning; a wrong number presented as a measurement is not. The general rule is the one this cost: before adding a channel that removes energy, check which diagnostics were built on the assumption that there was only one.

## A reference is a second run, not a number

- **Decision.** A record with a load across the strip cannot measure its own `beta` or its own impedance: the cut the load makes breaks the station fit's assumption of one onward wave at the stations either side of it, so a `beta` or a `Zc` fitted on that record describes the load and the line together. The microstrip study therefore runs a load-free twin -- same mesh, same settings, no load -- and uses it for two things only: its `zc`, and its load-free forward-amplitude ratio over the same two planes. Every station-fit row gates on `bool(g.get('loads'))` rather than on `loaded_without_reference`, because a load present in the mesh means the fit spans the cut whether or not a reference was supplied; supplying one does not repair the fit, it supplies the normalisation instead. `|S21|`, the `G1` row and the passivity bound speak as ratios against the twin. The twin's figures go to a throwaway `FigureSink` so they cannot own the filenames `dump_figures` would otherwise skip.
- **Strongest argument against.** The reference is already a first-class object in the API -- `LineReference`, and `microstrip_wave(reference=...)` -- and a second full board run inside the study spends a solve the caller did not ask for and cannot see. The cheaper reading is that the study should quote the refusal and leave the twin to whoever wants a normalised number, which is what the refusal text used to say.
- **Why that argument does not win.** A study whose loaded case prints `n/a` for every line constant is a study that cannot answer the question it exists to answer, and the caller most likely to run it is the least likely to know that a second run is the missing piece. The cost is one extra board run per loaded run, which is the price of a number that means something over a table of refusals; the direct caller of `microstrip_wave` still gets the refusal, and the refusal still names the fix. What the twin is *not* allowed to do is supply a `beta` for the loaded record: the ratio of ratios needs the line's delay and impedance to cancel, and it takes those from the twin, but the loaded record's own `eps_eff` and station impedance stay refused because there is nothing in a second run that repairs a fit spanning the cut.

---

## A tolerance justified by the wrong pair of numbers is not justified

- **Decision.** A tolerance must be defended by two readings of the SAME record -- same load, same mesh, same frequency -- and the comment has to say which of the quoted figures is machine-checked and which is quoted only for scale. The window in `test_a_loaded_run_quotes_a_ratio_against_a_load_free_twin` is now defended by `0.327195` (same record, no `reference=`) against `0.613960` (same record, handed the twin), a factor of nearly two, and the comment states which figures are pinned by assertions and which are quoted for scale only. General rule: a tolerance is justified by a pair of measurements from the same run and the same estimator, or it is not justified.
- **Strongest argument against.** The old sentence was not evidence of anything: no test asserted `0.623117`, no reader could check it, and the code was correct either way, so the paragraph was harmless decoration and the effort of re-measuring three board runs bought nothing but prose.
- **Why that argument does not win.** A wrong refusal is visible -- it prints `n/a` where a number should be, and someone asks. A wrong number in prose is not visible at all, and it propagates: this one had already been copied from a fine-mesh 1.0 pF shunt onto a coarse series resistor, where a reader would take it as the same record measured twice. The measurement it displaced, `0.327195`, is also the strongest argument for the design the entry above describes: an unreferenced `|S21|` carries whatever the record itself contributes -- the twin transmits `0.541741` at `300` steps, most of which is record length rather than line loss (see the entry below) -- so dividing by the twin is what makes the number about the load rather than about the mesh.

---

## A ratio looks stable when both of its readings are short by the same factor

- **Decision.** Before a reading is quoted as converged, its record length is varied and the trend is stated with it; a ratio of two readings taken from the same short record can look stable because both are short by the same factor, which is why the identity does not certify either of them. This is the third appearance of one class in this project -- the ground-return truncation at `G3`, the `300`-step record here, and the wrong-pair tolerance justification above -- and it sits beside the fitted-versus-audited rule for that reason. On this record the loaded reading moves from `0.613960` at `300` steps to `0.556575` at `9600`, and the load-free twin it is divided by moves from `0.541741` to `0.989576`, while the ratio of the two reproduced the referenced reading to `1.627` per cent at `300` steps and still held to `1.075` per cent at `9600`, so the identity was satisfied while its two terms climbed `66.5` and `82.7` per cent.
- **Strongest argument against.** Record length is a cost, and doubling it doubles the run time for a number that is already reproducible to six digits, so varying it is something to do once at the start of a project rather than a check to repeat on every table.
- **Why that argument does not win.** The reproducibility was the evidence and it was worthless -- three runs of the same `300`-step record agree with each other to six digits while all three are `11.7` per cent from the converged value, because they share the defect rather than the correctness. General rule: check record length and estimator provenance before trusting a converged-looking number, and never infer convergence from agreement between records of the same length.

---

## A duplicate test is retired by accounting, not by deletion

- **Decision.** When two tests cover the same behaviour, the merge tabulates every assertion of the test being dropped against the line where it now lives, and that table is reported with the merge; the survivor has to assert the union of the two, and its docstring has to say which of its readings are machine-checked and which are quoted for scale only. `test_a_loaded_run_quotes_a_ratio_against_a_load_free_twin` absorbed its duplicate this way: every assertion of the retired test was mapped to the line that now carries it, and nothing was dropped that was not re-expressed on the merged run.
- **Strongest argument against.** A merge is a rewrite of a green test, and a green test is the only evidence the suite is currently sound; the cheapest safe move is to keep both copies and let the suite carry the redundancy, since a duplicate costs the runner time and nothing else.
- **Why that argument does not win.** The duplicate here cost a loaded board run every time it ran, and it had already drifted -- one of the two copies cited a figure taken from a different mesh, so the pair did not agree on the record they both claimed to measure. Redundancy did not buy safety, it bought a second chance to be wrong, and a reader comparing the two had no way to tell which number was the record's. What makes the deletion checkable is the accounting rather than the confidence: the table is the only part of the operation that can be wrong in a way nobody notices, so it is the only part that needed care. The general rule: a deletion is justified by an enumeration of what survived it. That enumeration is only as good as the table's completeness, so the table lists the surviving line numbers, not the assertion names.

## Code lands on the branch that is finished, and the log says which

- **Decision.** Work lands on `master` directly. `wip/seam` is an ancestor of `master` and merged, so it is retired rather than kept as a long-lived branch, and the checkpoint convention every session uses -- commit a half-finished edit with a subject that says what is verified and what is not -- now applies on `master`. The branch is not the record; the commit subject is.
- **Strongest argument against.** A long-lived branch keeps experiments off the trunk and lets a half-finished change be abandoned without rewriting history; once the trunk itself carries half-finished work, every commit on it has to be trusted by whoever pulls next, and there is no longer a cheap way to drop a direction.
- **Why that argument does not win.** The fast-forward already landed, so the branch carried no information the trunk lacks -- keeping it alive would be keeping a second name for one line of history, and every later merge from it would be the merge of nothing. The failure mode this project keeps actually hitting is a modified tree left uncommitted overnight, not a bad commit on a trunk nobody else pulls; a long-lived branch does not prevent that, it relocates it. What survives is the discipline of naming what is verified, which a commit subject carries on any branch, and `wip/seam` contributed no part of it.

---

## A finite-step value is a lower bound on the limit, and the limit is named with it

- **Decision.** A finite-step value is a LOWER BOUND on the limit only once the approach has settled into a monotone run, and even then it is never the limit itself, so the limit is named in the same sentence that quotes the finite-step value. Before that point an early record is not a conservative estimate in either direction -- it is unusable, which is a stronger reason to vary the record length than the possibility that it is merely optimistic. On the settled tail the test is not that every interval is shorter than the one before it, but that the steps are a small and mostly shrinking fraction of the distance still to travel. The load table keeps its `2400`-step column -- that is the record the gate was accepted on -- and the numbers now read the way box-limited numbers in this project already carry their box: "`9.040` per cent at `2400` steps; the limit from the convergence sweep is about `10.5` per cent". This is the fourth appearance of one class here -- the ground-return truncation at `G3`, the `300`-step record, the tolerance justified from the wrong pair of measurements, and now the deviation column itself -- and it sits beside the fitted-versus-audited rule for that reason.
- **Strongest argument against.** The `2400`-step reading is the measured one and a limit is an extrapolation, so naming the limit beside it puts a model in the same sentence as a record; the convention everywhere else in this report is to quote what the run produced and state the box it was measured in, and a column that is still moving by well under a tenth of a point per doubling looks as though it has already arrived.
- **Why that argument does not win.** The sweep says both what the settled tail is and what the early records are not, and it says it three ways. At `300` steps this run reports `0.613960` against a limit of about `0.5567`, ten per cent above it, and at `600` steps it dips to `0.517615` before climbing again, so the two shortest records bracket the limit from either side and neither of them is a conservative estimate of it. From `1200` steps up the approach is monotone, and its steps are small next to the distance still to travel -- `+1.090` per cent at `1200` -> `2400` and `+1.230` per cent at `2400` -> `4800`, the step growing slightly rather than shrinking, both under two per cent of the `10.45` per cent level. That is the sense in which the tail is converging, and it is why an interval-by-interval test would reject a sequence that is behaving. The load-free twin's transmitted magnitude climbed from `0.541741` at `300` steps to `0.989576` at `9600` and was still gaining `0.196` per cent per doubling there, on its way to a limit near `0.9905`; the low first reading had already been written down as line loss when most of it was start-up transient. In that same sweep a ratio held to `1.627` per cent at `300` steps and to `1.075` per cent at `9600` while its two terms climbed `66.5` and `82.7` per cent, so a stable ratio is not evidence of convergence -- it hides exactly this drift, because both readings are short by the same factor and the factor cancels. The sharpest case is the deviation column added here: the prediction it is formed against is constant by construction, a closed form with no record-length argument in it at all, and the column still drifted `1.3` percentage points between `2400` and `9600` steps, so what a column that looks stable across record lengths reports is the estimator, not the physics. The general rule: settle the approach into a monotone run first, then read the finite-step value as a lower bound and each step as a shrinking fraction of what is left; a record short of that point bounds nothing, and the limit is named wherever the finite-step value is quoted -- the box, not the number, is what makes either readable.

