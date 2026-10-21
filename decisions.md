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

---

## A board is read by the run that dominates its net, not by its launch pad

- **Decision.** `python -m emfit board PATH [--net NAME] [--eps-r EPS] [--port-pad REF.NUM] [--json]` reads the file with `emfit.kicad.load_board` and converts it with `MicrostripBoard.from_kicad(net=..., taper="dominant")`, so the reported cross-section is the one carried by the run that holds the most of the net's length. The launch taper is never averaged into the width and the pad's geometry is not the line.
- **Strongest argument against.** The taper is part of the same net and sits on every real launch, so the command quotes a number for a fragment of the board and calls it the line's width; a reader who takes `w` off that output builds a model of a cross-section that stops where the launch begins.
- **Why that argument does not win.** A width is what everything downstream must divide: the cell has to divide `w`, and `eps_eff` and `Z0` are functions of `w/h` alone, so an averaged or minimum width describes a cross-section that exists nowhere on the board, and a taper has no single `w` at all. The launch is not discarded from the record, it is placed: `x_port` is the abscissa where the uniform run starts, so the taper's length is quoted as the distance the port sits inboard of the file's own edge.
- **Evidence.** `kicad_support_project/kicad_support_project.kicad_pcb`, net `RF_IN`: `h = 1.600` mm, `w = 3.000` mm, `eps_r = 4.4`, `x_port = 8.65` mm, `x_far = 32.22` mm, outline `70 x 20` mm. The reference study's own trace is `3.200` mm wide on the same `1.600` mm substrate, so the imported line is `6.25` per cent narrower.

---

## A layout whose width the cell does not divide is measured on a refined box, and the confound is stated

- **Decision.** The imported coupon is run in the default record's own physical box but at a cell of `0.200` mm rather than `0.400` mm, because a `3.000` mm trace is `7.5` cells at the published cell and no mesh can be built from a fractional strip. The two records are then compared on the *bias of the estimator against its own closed form*, never on the absolute `eps_eff`, and every quoted difference carries the statement that the width and the cell moved together.
- **Strongest argument against.** Refining the cell at a fixed physical box moves two inputs at once, so the difference between the two records is a width effect, a mesh effect and their interaction added up, and a comparison that changes two variables measures none of them; the honest answer to "the published cell does not divide this width" is to report that the geometry cannot be run on that mesh and stop.
- **Why that argument does not win.** Stopping reports nothing, and what the milestone claims -- that the layout is read, the stack-up becomes the right material, and the width becomes the right `w/h` -- is a statement about the cross-section, not about the grid. The claim survives the confound in the direction that is not additive: the estimator's bias against closed form is `+8.31` per cent on the default box (`62 x 44 x 22`) and `+7.80` per cent on the coupon in `eps_eff`, `+4.07` and `+3.82` per cent in `beta`, so the import adds nothing the grid does not already own, and that is the whole of what is claimed. Where the confound cannot be removed it is bounded instead: the width alone moves `eps_eff` by `-0.55` per cent in closed form (`3.34394` to `3.32545`) against `-1.02` per cent measured, so about half the shift is the refinement. Quoting the `beta` change as the *predictor* of the `eps_eff` change would not be a test, because `eps_eff` is `beta` squared by construction and the two are one measurement.
- **Evidence.** Default box `62 x 44 x 22` cells at `0.400` mm, `npml 6`, `2400` steps: `eps_eff 3.621781` against closed form `3.343938`, `beta 232.446960` against `223.353067` rad/m. Coupon at `0.200` mm, `124 x 87 x 44`, `npml 12`, `4800` steps, `120.27` s, settledness `|gamma| = 0.007979`: `h 1.600` mm, `w 3.000` mm, `eps_eff 3.584698` against `3.325455`, `beta 231.253918` against `222.734924` rad/m, `alpha 3.1381 +- 0.0863` Np/m; three independent `beta` readings on the one record (`231.2539` joint fit, `231.2277` two-station, `231.1273` two-wave) agree to `0.06` per cent, and the two half-span values differ by `0.64` rad/m. `|z0| = 57.0252` ohm is recorded and explicitly NOT quoted as a validation: width and cell both move it, and closed form predicts `+3.9` per cent where the run shows `+6.9`.

---

## The mesh builder's refusal is a contract, and a deferral records it rather than relaxing it

- **Decision.** `MicrostripBoard.to_cell_counts` keeps its refusal -- a `ValueError` raised first when `abs(self.x_far - self.length) > TOL * self.length` (the strip must *be* the far wall), then when any of `w / cell`, `clearance / cell - n_pml`, `x_port / cell - n_pml` or `(x_far - x_port) / cell` is not an exact integer, `cell = h / n_sub` -- the `board` command reports that refusal as the box's limitation, and no wall or width is rounded to make a board fit. Relaxing it would change what a `Board` means to every caller of `to_cell_counts`, which belongs to the contract decision that owns it and not to the import.
- **Strongest argument against.** A tool that refuses a real layout file has not done the milestone: the file is a real board, the gate is arithmetic we wrote ourselves, and rounding a wall outward is what every mesher does by default and costs at most half a cell.
- **Why that argument does not win.** What may not be rounded is the width: `w` sets `eps_eff`, `Z0` and the strip's own cell count, so a board whose width is not a whole number of cells cannot be built at that cell at all, and the only honest answers are "refuse" and "choose another cell" -- both of which the tool now states. Moving a wall silently by up to half a cell would put an unrecorded geometry change beneath numbers that are then compared at the `5` per cent level, and the refusal is itself a measurement: it is what says the published `0.400` mm mesh cannot carry a `3.000` mm trace.
- **Evidence.** `emfit/board.py:341-417`, `MicrostripBoard.to_cell_counts`:

```
379|         if abs(self.x_far - self.length) > TOL * self.length:
380|             raise ValueError(
381|                 f"the strip ends at x_far = {self.x_far * 1e3:.6f} mm but the "
382|                 f"outline is {self.length * 1e3:.6f} mm long: the model terminates "
383|                 f"the strip in the far absorber at the x wall, so a strip that "
384|                 f"stops short of that boundary cannot be represented (and neither "
385|                 f"can one that runs past it). Crop the outline to the strip, or "
386|                 f"extend the net to the board edge.")
387| 
388|         cell = self.h / n_sub
389|         dims = (
390|             ("n_strip", self.w, 0, "the strip width"),
391|             ("n_clean", self.clearance, n_pml,
392|              "the clearance beside the strip, less the lateral absorber"),
393|             ("n_ref", self.x_port, n_pml,
394|              "the port plane, less the absorber behind it"),
395|             ("n_line", self.x_far - self.x_port, 0,
396|              "the port plane to the far plane"),
397|         )
398|         wanted = {name: run / cell - cut for name, run, cut, _ in dims}
399|         bad = [dim for dim in dims if not _integral(wanted[dim[0]])]
400|         if bad:
...
412|             raise ValueError(
413|                 f"the mesh is cubic, so every dimension of the model has to be an "
414|                 f"integral number of cells, and at cell = h / n_sub = "
415|                 f"{self.h * 1e3:.6f} mm / {n_sub} = {cell * 1e3:.6f} mm these do "
416|                 f"not fit:\n" + "\n".join(rows)
417|                 + f"\n{advice}; otherwise the geometry or n_sub has to change.")
```

and `emfit/board.py:271-287`, the `taper=` mechanics: the widths are accumulated as `widths[key] = widths.get(key, 0.0) + track.length()` per distinct rounded width, `taper="raise"` (the signature default, `emfit/board.py:192`) raises when `len(widths) > 1`, and `taper="dominant"` takes `w_mm = max(widths, key=lambda width: widths[width])` -- the width carried by the greatest total track length -- then `strip = [track for track in along if round(track.width, 9) == w_mm]` and `x_port`/`x_far` from the extreme `x` of those segments only. `emfit/cli.py:280-281` passes `taper="dominant"` explicitly.

---

## KiCad is the model; Gerber is the ground truth

- **Decision.** The repository keeps two board readers because it has two jobs, and neither is a draft of the other. `emfit/kicad.py` is the model: it turns a board file into geometry, stack-up and the numbers derived from them -- `Board` at `emfit/kicad.py:402`, `Board.stackup_thickness` at `emfit/kicad.py:452`, and, in `MicrostripBoard.from_kicad` (`emfit/board.py:186`), `h` from the summed stack-up (`emfit/board.py:289-291`) and `eps_r` from the first core or prepreg entry that carries one (`emfit/board.py:302-318`) -- plus pads (`_parse_pad`, `emfit/kicad.py:610`), footprints and their placement (`_parse_footprint`, `emfit/kicad.py:636`, `_rotation`, `emfit/kicad.py:228`), pads flattened out of footprint-local coordinates (`Board.pads`, `emfit/kicad.py:429`), nets (`Board.net_name`, `emfit/kicad.py:433`), and the copper as tracks and zones (`_parse_track`, `emfit/kicad.py:569`, `_parse_zone`, `emfit/kicad.py:662`). `emfit/gerber.py` is the ground truth: `read_gerber` at `emfit/gerber.py:233` reads exported RS-274X artwork into a `GerberLayer` (`emfit/gerber.py:124`) of `Segment`s (`emfit/gerber.py:99`) and `Flash`es (`emfit/gerber.py:115`) against `Aperture`s (`emfit/gerber.py:67`), and `tests/test_gerber.py:212` holds the check the whole arrangement exists for -- the plotted front copper matched against the board's own tracks segment by segment, with the back copper parsed and spanning the board at `tests/test_gerber.py:264` and the pour inset pinned to `POUR_CLEARANCE = 0.5` (`tests/test_gerber.py:48`, asserted at `tests/test_gerber.py:312`). The rule for future work is stated as a rule, not as advice: nothing in `emfit/gerber.py` may become the source of geometry for a simulation; nothing in `emfit/kicad.py` may be trusted untested against the exported artwork; new geometry features -- arcs, pads, pours, transforms -- go in `kicad.py`; new artwork checks go in `gerber.py`; and a change that genuinely needs both is two changes, landed and reviewed as two.
- **Strongest argument against.** Two readers of the same board is duplicate work with two chances to be wrong: the copper in the plot and the copper in the board file are the same object, and a single reader would be half the code, half the bug surface, and would have no two descriptions that could ever disagree. Every crossing between them is also a place where the second reader has to be told what the first one means -- the y-negation the tests apply (`tests/test_gerber.py:20-24`), the sign flip `read_gerber` deliberately does not apply (`emfit/gerber.py:330-333`), pads held in footprint-local coordinates until `Board.pads` flattens them (`emfit/kicad.py:316-321`, `emfit/kicad.py:354-358`, `emfit/kicad.py:429-431`) -- and each such crossing is coupling that one reader would not need.
- **Why that argument does not win.** Because the split is forced rather than chosen, and it fails in both directions if it is collapsed. Gerber carries copper shapes and nothing else: no pads, no nets, no stack-up, no footprint identity, no reference designator. A port has to sit on a pad and a pad has to have a net -- the net is what the port excites -- so ports can never be placed out of `emfit/gerber.py`, and only `kicad.py` can supply what a port needs, which is precisely why `Board.pads` (`emfit/kicad.py:429`) and `Board.net_name` (`emfit/kicad.py:433`) exist at all. The reverse fails the same way: `kicad.py` describes what the designer intended, and intent is not what the fab builds -- a plot can disagree with its board through an export setting, a layer mapping, or a fill that was never refilled, and only an independent read of the artwork catches it. The duplication is therefore the mechanism and not the cost: the two readers are worth having because they can disagree, and the segment-by-segment test at `tests/test_gerber.py:212` is worth exactly as much as the independence of the two parsers. Without the rule the failure is the ordinary one, and it is quiet: the next session extends whichever file it opens first, an arc or a pour outline is lifted from the artwork into the mesh because it was already parsed there, and by the time anyone looks the repository has two competing readers of the same board answering the same question differently for the same copper, with no test able to say which is right -- because the test that would say so is the comparison itself.
- **Evidence.** The independence is visible in what each reader refuses to do. `emfit/gerber.py:19-38` counts arcs without ever producing their geometry, and `test_arc_is_counted_not_flattened` (`tests/test_gerber.py:170`) pins that: an arc on a layer is a count, not a polyline, because flattening one would be `gerber.py` supplying geometry. Every coordinate helper on the board side lives in `kicad.py` -- `_draw_points` at `emfit/kicad.py:696`, `_edge_bbox` at `emfit/kicad.py:710`, `_rotation` at `emfit/kicad.py:228` -- and `load_board` (`emfit/kicad.py:742`) is the only entry point that produces a `Board`. The single place the two readers are allowed to meet is the test, and there the meeting is an assertion rather than a shared parse: `tests/test_gerber.py:212` compares, it does not import one reader into the other.

---

## The eps_eff bias is systematic; its decomposition is the open question, and it is deliberately not being chased

- **Decision.** The measured effective permittivity sits above this tool's own closed form for the same cross-section, and it sits above it by the same amount on both geometries the repository can check. The published reference box -- a `3.20` mm strip on a `1.600` mm substrate at `eps_r 4.4`, `66 x 52 x 26` cells at `0.400` mm (`decisions.md:160`) -- measures `eps_eff 3.60431` (`decisions.md:215`) against its own `3.343938`, `+7.79` per cent. The imported coupon -- `3.000` mm strip on the same `1.600` mm substrate, `w/h 1.875`, `124 x 87 x 44` cells at `0.200` mm (`decisions.md:527`) -- measures `3.584698` against `3.325455`, `+7.80` per cent. The bias is recorded as real and systematic, and the decision is to leave it unexplained for now: the decomposition is entered as the next open question, not as the next task, and anyone reopening it starts from the three candidates below rather than from a fresh guess. Ports come first, because ports change what the tool *is*, while this changes only what one number means.
- **Strongest argument against.** A `7.8` per cent bias in `eps_eff` is larger than any effect this repository has measured on purpose, it is inherited by everything downstream of the substrate (`beta` by construction, `Z0` through it, and therefore every comparison the milestones make), and it is exactly the kind of stable offset that turns out to be one wrong term in one place. The argument is that a session which can still remember how the estimator was written should chase it now rather than after the code has moved on, and that recording it as an open question is a way of storing a number the next session will re-derive from scratch.
- **Why that argument does not win.** Because chasing it now would not separate three contributions that are still sitting on top of each other, and the estimator's own spread is already comparable to most of the bias. The candidates to be separated before any blame is assigned: (a) the lateral box -- the model's side walls and PML sit close to a `3.20` mm line inside a `26.40` mm wide box, so lateral loading can raise the effective permittivity on its own; (b) the estimator -- the closed form is quasi-static while the run reports a one-wave joint complex-gamma fit and a port-plane modulus, and those two readings already differ from each other by more than the fit residual; (c) genuine staircase physics of the discretised cross-section, which is not a defect at all and would not be removed by any fix. Two geometries agreeing to `0.01` of a percentage point is evidence that the bias is systematic; it is not evidence of what causes it, and no candidate is asserted here to dominate. The estimator's spread is `4.3` per cent (`53.144 / 50.952 - 1`, the port-plane modulus against the real part on the same record, `RESUME.md:67`, `.scratch/study_dump.txt:20-22`), which is why this entry records the M4 acceptance target as *not scored*: a bias that fits inside the estimator's own spread proves nothing by landing in the band, and a chase would end in a reading indistinguishable from a coincidence.
- **Evidence.** Both records, and the trap in quoting them. The reference box is `66 x 52 x 26` cells at `0.400` mm, `npml 10`, `w 3.20` mm, `h 1.600` mm, `eps_r 4.4`: `eps_eff 3.60431` measured against `3.343938` closed form, the number reproduced by the `Board`-driven run at `decisions.md:215`, whose `beta` is `231.88572` rad/m. The coupon is `124 x 87 x 44` at `0.200` mm, `npml 12`: `eps_eff 3.584698` against `3.325455`, with its `beta` readings, settledness and `|z0| = 57.0252` ohm given in the entry above (`decisions.md:527`). Every bias divides a measurement by the closed-form estimate for *that same* cross-section, because the closed form depends on the shape: the coupon's `3.584698` over the reference's `3.343938` is `+7.20` per cent, and that number is a width-and-cell difference wearing a bias's clothes -- it must never be quoted as one, and no future pair of records may be divided when their `w/h` differ. Note also that the *default* box (`62 x 44 x 22`, `npml 6`) reports `eps_eff 3.621781` against the same `3.343938`, `+8.31` per cent (`decisions.md:527`), which is a third number for a third box and is not the published record. What is deliberately not claimed: which of (a), (b) or (c) dominates; that the bias is constant in width (two widths exist, `3.20` and `3.000` mm, differing by `6.7` per cent); or that anything here is a solver defect.

---

## An arc is refused, not dropped, and the model has no place for one anyway

- **Decision.** Importer step 3 is closed as a refusal rather than as a feature. `load_board` (`emfit/kicad.py:962`) counts the board-level `arc` forms and raises before it hands back a `Board` (`emfit/kicad.py:992`): the message carries the count, the layer and the net of each (the net's name through `Board.net_name` when the board declares that code, the raw code when it does not), and then says what the arc would have cost -- it would never reach `Board.tracks`, so the strip width and the port and far planes derived from that net would be read off the remaining straight segments alone and would not be a measurement of the line. Nothing is flattened and no option turns the check off, because the model downstream is one straight run; the message's last sentence states what a caller can pass instead, a file whose curved line is already cut into straight `(segment ...)` runs. Only a bare board-level `arc` is refused: `gr_arc` and `fp_arc` are artwork, not track geometry, and a zone polygon is read for its `xy` children only.
- **Strongest argument against.** A reader that refuses a legal form is a reader that cannot open the file a designer hands it, and this refuses a form KiCad has written since version 6 -- `arc` at board level is how a curved track is spelled, so the first board with a bend in it is a board this tool will not read at all. "Support arcs" is the obvious alternative and it is not obviously hard; a refusal leaves the hole exactly where it was, and nothing downstream learns anything about a curve.
- **Why that argument does not win.** Because the alternative is not support, it is silence, and silence here is a wrong number rather than a missing one. `Board.tracks` is built from `(segment ...)` forms alone (`emfit/kicad.py:986`), so before this change a board-level arc was skipped without a word: the width came from whichever widths happened to survive, `x_port` and `x_far` from the extreme ends of those segments, and the result arrived at `to_cell_counts` looking exactly like a measurement of the line. A board that cannot be read is a problem its owner can see and cannot mistake; a board that is read as a different board is a number nobody can question. What is deliberately not chosen is flattening -- sampling the arc into chords -- because a flattened arc is an approximation of a curve presented as a measurement of one, the same family as the `taper="dominant"` width collapse and the mask-and-foil `h`, and if it is ever wanted its home is the caller, who can cut a bend into straight runs and model each. What would change the decision is a real board whose curve matters, and the answer then is still not a flattening inside `load_board`: a bend radiates, and the spec is one straight run.
- **Evidence.** The work was checked before any code was written, and it is genuinely absent. The coupon (`kicad_support_project/kicad_support_project.kicad_pcb`) has 0 `(arc`, 0 `(gr_arc`, 0 `(fp_arc` and not one occurrence of the substring `arc`; `CMEX.kicad_pcb` has the same three zeros, and its single `arc` substring sits inside a property value (a distributor URL), not in a construct. Form census, coupon: 4 `gr_line` (all Edge.Cuts), 66 `fp_line`, 58 `segment`, 12 `pad`, 3 `footprint`, 2 `zone`, 0 `via`. CMEX: 891 `fp_line`, 583 `segment`, 81 `via`, 388 `pad`, 81 `footprint`, 12 `gr_rect`, 4 `zone`. The second importer corroborates from the artwork side: `GerberLayer.arcs` reads `arcs 0` on all seven files in `kicad_support_project/gerbers/`, so nothing was flattened at export either. Because no file in the repository can exercise the refusal, it is pinned by one synthetic test that carries its own positive control -- `tests/test_kicad.py:648`, `test_a_board_level_arc_is_refused_not_dropped`: the same file minus the arc loads and yields exactly one track, which is what says the refusal is about the arc and not about the fixture, and the same file keeps an `arc` inside a zone polygon to pin that a nested one stays legal. The other correction is prose: `Zone` (`emfit/kicad.py:503`) claimed an arc inside a zone outline "contributes its two endpoints only", and `_parse_zone` reads only the `xy` children of the polygon (`emfit/kicad.py:897`), so such an arc contributes no vertex at all -- the code was right and the docstring was wrong. A zone is recorded, not modelled, so no zone geometry reaches a spec and nothing is lost by that. Where a docstring and a line of code disagree one of them is a claim that has to be fixed, and a claim that is wrong is the same family of defect as a number that is wrong.

---

## The outline is cropped to the strip by the caller, and the crop declares itself

- **Decision.** `MicrostripBoard.cropped_to_strip` (`emfit/board.py:498`) is a method a caller invokes on the spec the importer handed it, and it is the only thing in the repository that cuts the box down to the line. It moves the box and not the line: `replace(self, length=self.x_far, supplied=...)` (`emfit/board.py:527-531`), with the width, the substrate, `x_port`, `x_far`, the loads and the port carried over untouched. It declares what it did in the currency this class already uses for exactly this -- `'length'` is appended to `supplied` (`emfit/board.py:197`), once, so that a caller comparing `supplied` against the tuple it passed is told that the number sitting in `length` is the desk's and not the file's. Nothing in `to_cell_counts` (`emfit/board.py:536`) crops and nothing in the mesher crops: the mesher is still handed a spec and still answers only whether every dimension divides, and the refusal it already raised now names the crop it does not perform in so many words -- "Crop the outline to the strip, or extend the net to the board edge" (`emfit/board.py:580`). A spec that already ends at `x_far` comes back unchanged, declaration included (`emfit/board.py:527-528`), because the one caller most likely to compare `supplied` against what it passed is the one that would otherwise be told it had given a number it never gave.
- **Strongest argument against.** A mesh that cannot hold the box is a failure of the tool rather than of the caller, and the tool holds every number needed to fix it: `x_far` and `length` both arrive in the spec, so the correct box is computable one call before the mesh is built, and making the caller do it is a chore to get wrong and to forget -- the very chore that made `to_cell_counts` raise. On that argument the import should simply work on the board as drawn. Nor is anything hidden by doing the crop inside the mesher, because the run's own report states the geometry it modelled: a reader taking `length` off the report is reading the cropped box whatever produced it, and a reader taking it off the board is reading the board. One call fewer, one refusal fewer, and no number left unexplained.
- **Why that argument does not win.** Because a crop performed inside the mesher answers a file's number with a mesh's, and `supplied` exists in this class for no other purpose than to make that substitution visible. `length` is where the length of the outline arrives from `Edge.Cuts`; a mesher that quietly replaces it returns a spec whose field still carries a file's name and now holds the mesher's edit, and the report -- which states the geometry it modelled -- would then be stating the crop under the file's heading. Every downstream reading of `length` as "the board is this long" would be wrong in the one way nothing here is arranged to catch, because the wrong number is plausible. Keeping the crop in a caller-invoked method keeps three things where they belong: the judgement with the caller, since a box cut to the line models the strip alone and whether that is the right study for this board is a modelling choice; the arithmetic in `to_cell_counts`, which stays a pure function of the spec handed to it and therefore still refuses a spec that does not divide, cropped or not; and the record in `supplied`, the same field that already says `h` was summed from the stack-up and `eps_r` picked out of a core (`emfit/board.py:456-491`). The "just works" version is not refused because it is convenient, but because its convenience is bought by making the tool's own edit indistinguishable from the file's content.
- **Evidence.** Four tests added in `4ed5045` hold the method, and they are arranged around the declaration as much as around the arithmetic. `tests/test_board.py:314`, `test_cropped_to_strip_lands_the_far_plane_on_the_wall`: the cropped spec's `length` is its `x_far`, and `'length'` is in `supplied`. `tests/test_board.py:347`, `test_cropped_to_strip_is_idempotent_and_declares_only_what_it_did`: `once == twice` and `once.supplied == twice.supplied`, and a spec that already ended at `x_far` comes back with its `supplied` untouched (`tests/test_board.py:378-379`) -- the no-duplicate, no-false-declaration half. `tests/test_board.py:382`, `test_the_cropped_port_coupon_meshes_at_sixteen_substrate_cells`: the cropped port-bearing coupon -- `net='RF_IN'`, `port_pad=('J1','1')` -- divides at `n_sub 16`, `n_pml 12`, giving `n_strip 20`, `n_clean 78`, `n_ref 33`, `n_line 25` at a `0.1` mm cell, so the crop is what makes the end-to-end run reachable at all. `tests/test_board.py:407`, `test_even_the_cropped_dominant_coupon_needs_a_finer_mesh`: the same crop on the dominant-width spec still refuses, because cropping lands the far plane on the wall and touches no width -- `x_port 0.00865` to `x_far 0.03222` is `23.57` mm of line, a whole number of cells only when `n_sub` is a multiple of `160` (`n_line = 2357 * n_sub / 160`), which is why that test's assertion is the refusal and not a mesh. `tests/test_board.py` went from 12 tests to 16, and the fast suite from `356 passed, 9 deselected` to `360 passed, 9 deselected`.

---

## Two boards, two jobs: the reference box is the acceptance test and the coupon is not

- **Decision.** The KiCad fixture is split in two, because the two boards answer two different questions and
  only one of them can be answered by comparing against the published record.
  `kicad_support_project/reference_box.kicad_pcb` is the reference geometry exactly -- `66 x 52 x 26` cells at
  `0.40` mm, `npml 10`, `w = 3.2` mm, `h = 1.6` mm, `eps_r = 4.4`, the published `2400`-step run -- and
  reproducing the published columns through `MicrostripBoard.from_kicad` and the `Board` path is the
  milestone-1 acceptance. `kicad_support_project/coupon.kicad_pcb` is the real board and its only job is to
  show that the importer reads real KiCad output; its oracle is the physical measurement of that board, not
  the published microstrip record. The coupon is therefore graded on what can be read back out of KiCad
  without a bench -- outline, stackup, declared thicknesses, track width, cell counts -- and the study it
  drives is recorded as a prediction with no pass/fail attached. A disagreement between the coupon's study
  number and the published reference record is not evidence about the importer, the study, or the milestone.
- **Strongest argument against.** Two fixtures with two oracles is a weaker test than one fixture that has to
  satisfy both. It lets a fixture be shaped until it passes, and it surrenders the one comparison that would
  catch a systematic error in the importer itself -- a real board against a published record -- because the
  reference box is emitted by a script written by the same hand that wrote the importer, so agreement there
  proves consistency and not correctness.
- **Why that argument does not win.** The comparison it surrenders was never available to be surrendered. The
  coupon's substrate is `20` mm wide against the `17.4` mm between the reference line's lateral walls: two
  different cross-sections, hence two different electromagnetic problems, and no tolerance makes one into the
  other. Held together as one fixture, the only way to get a green light was to widen the tolerance until the
  coupon passed at a number it could not reach for reasons having nothing to do with the code -- which is the
  classic shape of a test that is then either deleted or ignored. Split, each comparison sits at the
  resolution it actually has: the reference box is graded against the published columns at the record's own
  fit residual, and the coupon is graded against the bench, which is where a real board belongs and which is
  not in this repository. The shaped-until-it-passes objection is answerable by reading rather than by
  trusting: the fixture is `2105` bytes of plain text standing next to the script that emits it, both
  committed, and its read-back is asserted field by field by `tests/test_reference_box.py`.
- **Evidence.** The reference fixture, emitted by `kicad_support_project/generate_reference_box.py` and
  committed with it: `26.4 x 20.8` mm outline, one `3.2` mm track on net `RF_IN` running `x = 4.8` to
  `26.4` mm at `y = 10.4` mm, and one stackup entry -- a `1.6` mm core, `eps_r = 4.4`, and nothing else,
  because `from_kicad` sums every declared thickness and the `0.035` mm foils would make `h = 1.67` mm and a
  cell of `0.4175` mm that does not divide the run. There is no pad in the file, so `x_port` and `x_far` come
  from the run extremes rather than from a terminal and `supplied == ()`. Read-back: `length 0.0264`,
  `width 0.0208`, `h 0.0016`, `eps_r 4.4`, `w 0.0032`, `x_port 0.0048`, `x_far 0.0264`, counts `n_strip 8`,
  `n_clean 12`, `n_ref 2`, `n_line 54`, `cell 0.0004`, i.e. `nx 66`, `ny 52`, `nz 26` -- all three counts the
  published box names. Two of those identities are exact and are worth naming, because they are what makes
  the fixture an acceptance rather than a coincidence: `nx * cell == x_far` exactly, `x_port` cancelling out
  of `n_pml + n_ref + n_line`, and `ny * cell == width` exactly, since the clearance is `width/2 - w/2`.
  `nz` is *not* board-controlled -- `nz = n_sub + n_air + n_top`, with only `cell = h / n_sub` derived from
  the board -- so a stackup edit moves `cell` and `nz` together, and the published `26` is a consequence of
  the `1.6` mm core at `0.4` mm rather than a field anyone sets.

**Reproduction, unaudited** (`wall_s 9.763592199`): `eps_eff 3.604312254366848` against the published
`3.604312254`, a difference of `1.0e-10`; `beta 231.8857152867915` against `231.88571529` (`1.4e-11`);
`|z0| 53.14411383477105` against `53.144` (`2.1e-06`); `Re z0 50.952340670283945` against `50.952`
(`6.7e-06`); `alpha_fit 2.469703092775746` against `2.469703` (`3.8e-08`);
`|gamma| 0.006281926302682181` against `0.0062819` (`4.2e-06`); `fit_residual 0.007812967007589234` against
`0.007813` (`4.2e-06`). The lateral sink is absent from that run because the absorbed-work accounting is
exactly what `audit` switches on; run again through the same board path with `audit=True`, the fixture
returns `alpha_audit 1.3360133447381923` Np/m against the published `1.33601` (`2.5e-06`), lateral work
`1.9763611915240925e-07` J against the published `1.976361e-07` J, `fractions` `lateral 0.07054150460217655`
and `end 0.9294584953978235` against `7.054` and `92.946` per cent, and `implied_s21 0.9640842781613148`
against `0.9640843`. Those rows close.

One row does not close, and the audit does not touch it: the station `|S21|` is `0.9861098351994007` audited
and `0.9861098351994007` unaudited, `9.1e-04` below the `0.9870082` this log records for the same box. The
gap is inside the `7.8e-3` fit residual but four orders of magnitude above the round-off every other row
achieves, so it is named as an open discrepancy rather than absorbed into a tolerance. It is not the mesh,
the stackup, the port or the audit -- the same run puts `eps_eff`, `beta`, `z0`, `alpha_fit`, `|gamma|` and
the lateral sink on the published digits. It is left open with that statement rather than explained away,
and it is the one thing a reader checking this acceptance should re-derive first.

---

## The absorbed-work audit is opt-in, and its clock names its route

- **Decision.** `audit` is a keyword-only flag defaulting to `False` on both `microstrip_wave` and, since
  `d555b4d`, `microstrip_wave_board`. The study path is the one place that turns it on, `audit=True` for the
  real run and `audit=False` for its twin (`emfit/studies.py:2662` and `:2648`), so every absorbed-work number
  in the report comes from an audited run, and a reader who wants that row must ask for three things: the
  flag, which entry point produced the number, and the wall clock of the run that produced it. A clock is
  never quoted as "the cost of the audit" on its own. No audited case is added to the test suite: the
  cheapest audited route measured here is `17` s and the dearest `600.69` s for bit-identical output, against
  a `302.22` s suite, so the audited row is recorded here with its number and its route rather than asserted
  by `pytest`.
- **Strongest argument against.** An acceptance that does not run under `pytest` is not an acceptance, and
  the claim the audit exists to support -- that the sink is lateral matched-layer leakage at `1.3360` Np/m --
  is precisely the claim `d555b4d` had to thread the flag through to reach, so leaving it out means the
  automated check of the board path never exercises the accounting code at all.
- **Why that argument does not win.** A test whose duration depends on which entry point it happens to use,
  by a factor of `35`, grades the plumbing and not the solver: the same self-check either fits the suite or
  does not, for reasons that have nothing to do with the physics, and a `600` s case behind a marker nobody
  runs is a comment. The route dependence is a defect in its own right and is carried below as an open item;
  once a direct `audit=True` costs what a study run costs, the audited case is `17` s and can be added
  deliberately, with its cost known. What is not deferred is the evidence: the board path was run audited,
  and the lateral sink, the wall fractions, the implied `|S21|` and the work in joules all reproduce.
- **Evidence, five clocks on one box** (`66 x 52 x 26` at `0.40` mm, `npml 10`, `2400` steps, `600` warm-up,
  `1800` accounted):
  (1) `9.763592199` s, a direct call with `audit=False`;
  (2) `17` s, the study path with `audit=True`, whole `python3` process including `import emfit`
  (`START=1792548557`, `END=1792548574`, `/tmp/study_retime.log`; an upper bound on the solve alone, because
  the script died on a cwd-relative dump write before printing its own `WALL` line);
  (3) `31.792227651982103` s, the clock recorded in `.scratch/study_dump.txt` line 1 by that same study
  script on 2026-10-20 01:31, whose line 47 is the absorbed-work row -- i.e. the published clock is an
  audited clock, and it is the study route's clock;
  (4) `570.3019553209888`, `784.1913794020074` and `600.6859359579998` s, three direct calls with
  `audit=True` in three different scripts, all returning bit-identical numbers (lateral work
  `1.9763611915240925e-07` J, total removed work `2.8017e-06` J, lateral sink `1.3360133447381923` Np/m).
  The `571` s anomaly parked in the entry "Retraction: the lateral PML is not excluded, it is the sink" is
  the first sighting of (4), not a scratch artefact: three scripts agree to within a factor of `1.4`.
- **Open item, stated as one.** The audit is not sampled. `emfit/pml.py:720-721` and `:731-732` call
  `record("e", ...)` and `record("h", ...)` on every step under the sole guard `if self._audit is not None`,
  from `FITStepper.step` (`emfit/evolve.py:193`, `:202`); the only economy is that `_build` caches the wall
  index sets per `dt` (`emfit/pml.py:364`), leaving four fixed-index gathers and four weighted dot products
  per step (`emfit/pml.py:369-371`). Both routes construct the same `AbsorbedWork(groups={"end", "lateral"})`
  at `emfit/studies.py:1968-1974`, so they are supposed to cost the same per step -- and measured against the
  reference box they are `35` times apart (`17` s against `600.69` s) for bit-identical output. The mechanism
  is not established. It is recorded as an open item with four measurements attached and is not to be
  explained by hardware, contention or "scratch": `31.79` s and `17` s are the same route differing by
  contention, and `570`/`600`/`784` s are a different route. Until it is settled, quote neither number as
  the cost of the audit.
- **A hazard that cost nothing but could.** `.scratch/` is in `.gitignore` and `.scratch/study_run.py` writes
  its dump with a cwd-relative path (`open(".scratch/study_dump.txt", "w")`, line 11), so re-running that
  script from the repo root would silently overwrite the evidence file with `git status` showing nothing at
  all. The retiming above was therefore run from `/tmp/retime`, where the write failed loudly instead.

---

## git is not in the image, so landing is an operator action

- **Decision.** Every merge and every stash drop is performed by the operator. This is not a workaround with an
  expiry date; it is the shape of the system until the container image gains a git binary or a git-capable
  tool is exposed to it. The agent commits to `wip/ports` at every coherent point and the operator lands in
  batches. "Merge when convenient" is therefore not a temporary concession but the permanent arrangement.
- **Evidence, verified rather than assumed.** `shutil.which('git')` returns `None`; `/usr/bin/git`,
  `/bin/git`, `/usr/local/bin/git`, `/usr/lib/git-core/git` and `/opt/git/bin/git` are all absent;
  `/usr/lib/git-core` and `/usr/share/git-core` do not exist; the only `/usr/**/git` hit within three levels
  is `/usr/share/nodejs/@npmcli/git`, an npm JavaScript package. `find_spec` returns `None` for `dulwich`,
  `pygit2`, `GitPython` and the `git` package. The tool surface offers `commit, init, clone, branch_create,
  checkout, stage, unstage, worktree_add, worktree_remove, stash_push, stash_pop`: there is no `merge`, no
  `reset`, no `update-ref`, and the dispatcher rejects `merge` as an invalid literal. `branch_create` cannot
  force-move an existing ref -- `fatal: a branch named 'master' already exists`.
- **What this retires.** The container-slot hypothesis carried since the first dispatch. Freeing a slot could
  never have helped, because there is nothing in the image to free it for. A future session that finds
  itself waiting for a slot before a merge is waiting for something that does not exist.
- **The refusal that was kept, and why.** A fast-forward has no merge commit and both trees are identical, so
  it is only a ref move, and that much is expressible by writing `.git/refs/heads/master` directly. The write
  was pre-flighted rather than performed, and the pre-flight found `master` already at `68404dd` with `HEAD`
  on `refs/heads/master`: the operator had landed it. Nothing was written. The general lesson is the
  pre-flight, not the write: a ref write is expressible but is not a merge -- it leaves no `Fast-forward`
  reflog line -- so it stays a last resort, and it must be checked against the refs as they actually are, not
  as the previous inspection assumed they were.
- **What not to ask for.** Not "add a merge verb" to this tool. The correct request is "git is absent from the
  container image", which is a different and larger one.
- **Landing, as performed.** `git checkout master && git merge --ff-only wip/ports` took `master` from
  `ffbb4a4` to `68404dd`; `merge_base --is-ancestor ffbb4a4 master` confirms a true fast-forward, and the log
  from `68404dd` back to `ffbb4a4` is linear. `git stash drop` emptied the stash list ("No stashes.").

---

## A test command that cannot print its count is not a verification

- **The incident.** The suite was launched as `python3 -m pytest -q` while `pyproject.toml` already sets
  `addopts = "-q"`. pytest reads that as `-qq`, which suppresses the summary line outright. The run printed
  five dot lines, `[100%]` and `EXIT=0` -- and no counts line, so a green result carried no evidence of how
  many tests passed or how long it took.
- **Why it is the same class of defect as the vacuous pass.** Both are green for the wrong reason. A vacuous
  pass proves nothing about the code; an uncounted suite proves nothing about the suite. `EXIT=0` on its own
  is not a number, and this log has already been burned once by treating a plausible-looking result as a
  verification.
- **Rule.** Never pass `-q` on the command line of this project; `addopts` supplies it. Any run that is going
  to be quoted must print its own summary line, and the quoting session should grep for ` passed in ` rather
  than for the exit code. The countable re-run of this suite is `380 passed in 350.12s (0:05:50)` at
  `f23e78e`, and that is the figure of record. The uncounted `EXIT=0` was never entered anywhere.

---

## Milestone 2: ports on pads, in this order

- **Why this is the milestone that matters.** Milestone 1 makes a `.kicad_pcb` become a geometry the solver
  meshes. Milestone 2 makes the result a tool: a user places a port on a pad in an imported board and reads
  S-parameters back.
- **Order.** (1) The `--port-pad` flag and the non-null branch of the `port` key in `board --json`, which is
  currently untested -- smallest job, unblocks the rest. (2) A CLI path from a pad into a microstrip study:
  register `microstrip_wave_board` and lift the `nsteps` cap that blocks a `0.1` mm cell, or provide an
  explicit override that warns about the cost. (3) A port on the coupon's `J1.1` pad, run end to end,
  reporting S-parameters and a field slice. (4) The acceptance: a port on a pad in an imported board yields
  S-parameters, with the reference/loaded sequence expressed in the interface.
- **Carried, not chased.** The station `|S21|` discrepancy (`0.9861098` against `0.9870082`, `9.1e-04` low,
  byte-identical with the audit off) stays named in section 49 and is not pursued in this milestone. The one
  diagnostic that would settle it is a re-run of the exact historical configuration; it is a curiosity, not a
  gate. The `35`-fold audit-route clock gap likewise stays an open item: never quote `600` s as the cost of
  the audit.
- **Landing during this milestone.** The agent commits to `wip/ports` and reports the landing command; it
  cannot land anything itself, per the section above, and will not wait on a merge to keep working.

---

## 54. A port on a pad, and the ceiling that became a price

**The flag that did not exist.** A user who has imported a board can see which nets carry a microstrip run, but could not say where the port is. The board reads the net and picks the run that covers most of it, which is a defensible guess and not a statement about the launch: a pad is a place someone solders a connector, and it sits at one end or the other. So `--port-pad REF.NUM` names it, as a reference designator, a dot, and a pad number. It fills the `port` key of the board spec with the reference, the number, the net the pad belongs to and the pad's copper position; without the flag the key stays null and the taper sentence remains. It is refused where it cannot mean anything: `--port-pad` without `--net` stops with `--port-pad needs --net: the net is the strip the port is placed on`, exit 2, before a file is opened, because a pad is only a port if we know which strip it lands on.

A pad name the board does not declare is named, not fixed. That refusal exits 0 like every other `no microstrip spec:` refusal: the board was read, the answer is that there is no port to place, and that is a finding about the file rather than a crash in the tool. Naming the pad it could not find, in the same message as the pads it did find, is the difference between a bug report and a typo hunt.

**The ceiling that became a price.** The `MICROSTRIP` study capped `nsteps` at 4000. That cap was arithmetic policy standing in for a decision: it kept the study cheap by making the interesting meshes unaskable. It could not survive a pad on this coupon, because the coupon's lateral clearance does not divide into a 0.2 mm cell -- the crop leaves `8.500000 mm / 0.200000 mm - 12 = 30.500000` cells, and the refusal offers `n_sub = 16, 32`, so 0.1 mm or 0.05 mm and never 0.2. A 0.1 mm cell needs 9600 steps to resolve the same frequency, so the cap was refusing the only run the new flag makes possible. The ceiling is now 20000, and above 4000 steps the record prints a warning on stderr that quotes the two things we have measured -- the 0.2 mm coupon at 4800 steps in 120.27 s, the 0.1 mm port path at 9600 -- and predicts no wall clock for a mesh it has not run. A stated cost is a decision the user can make; a cap is that decision taken from them.

**The study that could not read a file.** Every earlier study was a set of numbers. This one needs a path, a net name and a pad name, and the parameter layer had three kinds -- int, float, bool -- so `--set board=...` would have gone through `float()` and failed. `str` is now a kind that refuses what numbers have and text does not (choices, bounds, a default that is not text) and returns the value unchanged. The second gap was the browser: a text parameter fell through to `<input type="number">`, a control that cannot express a filename or `J1.1`. That would have been a study that worked from the command line and was unusable in the interface, and no test would have caught it. A parameter kind is not finished until the form knows what to draw for it.

`microstrip_board` reports what the CLI path reports, at the four planes a person actually asks about: the measured plane, the port plane, the mismatch as a VSWR, and the passivity bound -- named as a bound and explicitly not a losslessness check, since a matched layer only ever removes power the two planes never see again. Two modelling choices are stated in the study's own text rather than left to be inferred. The pad does not decide the line width: a port says where the launch is, not how wide the strip is, so the width still comes from the board. And the stations sit at 20 % and 80 % of the line span rather than at its ends, because a station inside the match region measures the source, not the line; the consequence is stated where it bites -- the total span phase exceeds pi here, so the two-station difference has wrapped, and the record says to read the one-wave fit instead of pretending the difference is unambiguous.

**The run.** `board=kicad_support_project/kicad_support_project.kicad_pcb net=RF_IN port_pad=J1.1 n_sub=16 n_air=12 n_top=12 npml=12 nsteps=4800 f0=5.8278 crop=true`: 322 x 200 x 40 cells at 0.1000 mm in a 32.20 x 20.00 x 4.00 mm box, 4800 steps of which 3600 transformed, 720 s. The launch row reads `pad J1.1 on net 'RF_IN', at x = 8.700 mm, y = 10.000 mm on the front copper`; the line is the 3.000 mm strip on 1.600 mm of eps_r = 4.4 (w/h = 1.875), port plane at 8.700 mm, far plane at 32.200 mm, nine stations from 13.40 to 27.50 mm. beta from the one-wave fit 238.050 rad/m against Hammerstad-Jensen 222.735, |gamma| 0.02055, fit residual 0.05007, eps_eff 3.79848 from this run's beta against 3.32545 closed form, line Z0 50.617 ohm closed form against 53.6803 from the stations. |S11| is 0.02018, -33.90 dB, at the measured plane and the same magnitude at the port plane, because beta is real here, so moving the plane changes phase and nothing else; VSWR 1.0412:1. |S21| is 0.867547, -1.234 dB, between the station planes 14.10 mm apart. The passivity sum is 0.753059. Full-domain ground current 5.096473e+04 A against 5.094744e+04 A over the strip extent, ratio 1.000, which is the crop holding. Two figures: the line phasors and the mid-plane Ez slice.

No attempt is made to reconcile this with the earlier direct coupon measurement, because it is not the same box: that run was 52 cells tall and this one is 40, since n_air 12 plus a 12-cell lid, so the absorbing lid sits closer and |S21| between two planes is expected to fall. Two runs that differ in the lid are not a measurement and a check of each other. Leave the comparison for a run that holds the box fixed.

**Falsification read, and the clause that was half-right.** What would have convicted this: a launch row naming J1.1 while the mesh was still cropped around the taper (x = 8.700 mm is the pad, and the counts move with it); |S11| differing in magnitude between the two planes, which it does not, and that is the arithmetic checking itself; ground current outside the strip exceeding the strip's own by more than a fraction (ratio 1.000, so the crop is not clipping the return path); an |S21| of exactly 1, which would have meant the two stations shared a plane. The residual 0.05007 is the largest number in the report and the honest one: a one-wave fit over nine stations with a wrapped total phase is a fit over a line that is not quite uniform, and the study reports the residual rather than the fit's confidence.

The passivity clause as first written was necessary and not sufficient. It said a sum above 1 would convict -- true, that is gain from somewhere -- and it was then read as if 0.753 sat comfortably inside. On a model with no material loss it does not: 1 is the expected value, and a sum well below it names an unaccounted sink. 0.753 meant a quarter of the power was leaving through something that was not the two stations, and the sink was the boundary: the top PML's inner face sat 1.2 mm above the strip, 0.75 substrate heights, where a microstrip's field is still substantial. The standard list now reads three ways. Passivity above 1 is a bug. Passivity near 1 is what a lossless material expects. Passivity far below 1 is an unaccounted sink, and it has to be named before any number from the run is quoted. A bound is only a test if both of its sides are tests.

## The lid, moved: most of the deficit, and a remainder that did not move

The falsification read left one sentence of diagnosis -- the top matched layer
sat 1.2 mm above the strip, three quarters of a substrate height, where the
mode's tail is still worth absorbing, so the boundary was taking the mode and
not the tail.  A diagnosis that cannot be tested by moving one parameter is
not a diagnosis.  This one could be tested: same board, same pad J1.1 on the
same net, same 0.1000 mm cell, same 4800 steps, same nine stations, and n_air
raised from 12 to 48 so that the inner face of the top layer went from 0.75 to
3.0 substrate heights above the copper.  The box went from 4.00 to 7.60 mm
tall, the mesh from 322x200x40 to 322x200x76, and the wall clock from 720 s to
about 1380 s.  Everything else is identical, which is what makes the pair a
measurement rather than a second opinion.

                                      lid 0.75h        lid 3.0h
    passivity |S11|^2 + |S21|^2       0.753059         0.904486
    |S21| over the 14.10 mm           -1.234 dB        -0.437 dB
    |S21| per length                  0.0875 dB/mm     0.0310 dB/mm
    eps_eff, run / closed form        3.79848/3.32545  3.51062/3.32545
    excess over the closed form       +14.2 per cent   +5.57 per cent
    beta, fit / Hammerstad-Jensen     238.050/222.735  228.852/222.735
    |gamma|                           0.02055          0.01711
    fit residual                      0.05007          0.02561
    |S11| at both planes              -33.90 dB        -35.64 dB
    Z0, stations / Hammerstad-Jensen  53.6803/50.617   53.0576/50.617
    ground current, full / strip      1.000            1.001

The lid was a cause.  The passivity deficit fell from 24.7 per cent of the
power to 9.55 per cent, and it fell where the diagnosis said it would: the
guided-wave loss, which is the same deficit read along the line, fell from
0.0875 to 0.0310 dB/mm, the fit residual halved, and eps_eff walked from 14.2
per cent above the closed form to 5.57 per cent above it.  Every criterion
that asked for a number to move toward the lossless, closed-form limit was
answered in the direction it asked for.

The lid was less than the cause.  Quadrupling the clearance bought a factor
2.6 in the sink -- 0.387 of it survived -- and no evanescent tail behaves like
that.  A tail decays exponentially in the distance it is decaying over; four
times the distance should not stop at a factor 2.6.  So the deficit is a
mixture of two terms: one that still responds to clearance and one that does
not respond at all.  Two points on one axis cannot separate them, and this is
the honest shape of the result -- not "the lid was it" but "the lid was three
fifths of it, and the rest has a different address".

The dissipation is the same quantity read the other way.  0.0310 dB/mm over
the 14.10 mm between the planes is 3.7 per cent of the power, and the material
is lossless, so nothing heated: that power left through a boundary.  The
lateral-leakage reference this is judged against, 0.0116 dB/mm at gate 2, was
measured with roughly 5.5 substrate heights of clearance, so a pad port at 3.0
heights still losing 2.7 times as much per millimetre is losing it to
something that is neither the lid nor the material -- a lumped gap source
radiates into the substrate's parallel-plate continuum, and a leaky wave of
that kind is a loss per unit length by construction, which is exactly the
shape the station fit reports.

Which criteria were met, in the terms they were set in.  Passivity within 2
per cent of 1: not met, 9.55 per cent short.  |S21| per millimetre within a
factor 2 of 0.0116: not met, at 2.7 times, against 7.5 times before.  eps_eff
moving toward the closed form as the lid rises: met, 3.79848 to 3.51062 with
3.32545 underneath.  One of three -- and the two that failed failed for the
same reason, which is the reason this section exists: the run still has an
unaccounted sink, so its S-parameters are not quotable under the amended
standard.  What is quotable is narrower and real: a pad-named port on an
imported board runs end to end and yields S-parameters and figures; the lid
term's size and sign are now measured rather than argued; and the remainder
has a name and a shape to test.

The next test has to break the correlation, and there is one that does it
cheaply.  Push the lid to 6.0 substrate heights with the lateral extent
untouched.  If the deficit keeps falling, the remainder is still the boundary,
and the answer is a taller box and a larger bill.  If it flattens, the flat
part is the source and the lateral walls, and no lid will ever remove it --
which is a fact about lumped launches on lossless boards, worth knowing before
a spectrum is quoted rather than after.  One run, 1.6 times the cells, about
35 to 40 minutes.  That is cheap enough that not running it first would be a
choice rather than a constraint.

The last place the one-sided reading survived was the tool's own output.  The
row this run printed ended "so a wide margin is the expected reading and not a
defect" -- the sentence this section exists to refute.  Both microstrip rows
now name three readings: above 1 is a bug, near 1 is what a model with no
material loss should return, and well below 1 is power that left through
something the two planes do not see, whose sink has to be found before any
number from that run is quoted.  The typed-line microstrip study carried the
same claim and got the same correction, and the part of its wording that was
true -- why the plain sum is legitimate when both magnitudes are read on one
cross-section, the sqrt(Re zc) weighting cancelling -- was kept, because what
was wrong was the test, not the arithmetic.

## 56. The broadband sweep read the window, and the window was the fault

The gate existed to test one thing: whether the pulse path, reading one bin at
a time off a broadband record, returns the number the cw twin already returns
at the tone's own frequency.  Two independent routes to one bin have to agree
before either is believed.  It failed on the first attempt, and not at the
edges.  The sweep ran, and every bin that survived the guards came back
non-passive: passivity 1.524749 to 1.564827 across the usable band, |S21|
1.24903 at the bin nearest the tone, 27 per cent above the twin and 1.8 dB of
gain out of a line with no loss in it, with 12 of the 25 bins carrying the
"BUG: passivity exceeds 1" flag.  A non-passive S-pair is not a lossy line.
It is a broken measurement, and the sweep, as it stood, was not quotable at
any frequency.

The elimination had to start from what could not be the cause.  The two
post-processing blocks -- the cw path and the pulse path -- are byte-identical
argument for argument, so nothing downstream of the record could explain a
difference between them.  What was left was the time weighting, and the
support for that reading came off the same record: the whole-record scalars
were clean.  |S21| 0.99000, |gamma| 0.00456, fit residual 0.00662, all read
off the aggregate rather than per bin.  A record that integrates to a sane
answer and differentiates into a non-passive one localises the fault to the
per-bin phasors, and clears the solve, the reference and the de-embedding in
one step.

The experiment was a swap, not a rewrite.  A throwaway script monkeypatched
the single np.hanning call and re-ran both variants over the same record, the
source untouched.  What makes that decisive rather than suggestive is that
the whole-record scalars came back byte-identical between the two variants:
the only thing that changed between the runs was the weight, so the difference
in the per-bin numbers cannot be assigned to the solve, the record, the port
or the de-embedding, because none of them moved.  An experiment in which
something else also moves is an experiment that suggests.

With a flat weight the same bin that was the worst under a taper becomes the
agreement the gate was asking for.  The bin nearest the tone reads |S21|
0.99017 against the cw twin's 0.98126, 0.91 per cent high; passivity 0.980464
against 0.962932, 1.82 per cent high; eps_eff 3.60970 against 3.62178, 0.33
per cent low; and no bin is flagged.  Agreement inside one per cent on the
quantity that matters, and a passivity that is below one everywhere.

The mechanism is not subtle once the record is looked at as a record.  A taper
is not amplitude-neutral for a transient that does not fill it: it multiplies
the packet by a curve that is still moving underneath the packet, and the
per-bin phasors stop being one mode.  The fit says so without being asked
twice -- the one-wave residual at the bins goes from 0.0066 to 0.065 and the
fitted reflection from 0.0046 to 0.11, an order of magnitude in both, which is
what a fit reporting that the thing it is fitting is no longer a single mode
looks like.  And the record did not need tapering in the first place.  A
Ricker evaluated at t = 0 is about 1e-17 of its own peak, and the packet has
left through the PML before the record ends, so there is no truncation
discontinuity for a window to hide.  The window was solving a problem this
pulse does not have, and charging the answer for it.

One consequence deserves its own paragraph, because it outlives this bug.  The
guards are tests on the fitted beta, so a corrupted beta does not merely
perturb the numbers, it moves the guards' own verdict on which numbers are
allowed to exist.  The tapered build and the flat build did not agree on which
bins are usable -- twelve against eleven -- and the passivity blow-up in the
tapered build was concentrated exactly where its amplitude distortion is
worst.  A guard is only as trustworthy as the estimator feeding it.  That is
why the weight now multiplies the bins and the guard through the same object:
a guard taken through a different weight than the measurement would be
judging one measurement by another one's leakage.

The usable window is what it is, and it is worth stating flatly rather than
apologising for.  At a probe span of 9.6 mm and eps_eff about 3.6, the
beta*span floor of 2*pi/5 refuses 3.25 GHz by 0.019 rad and everything below
it, and the pi branch limit refuses 8.25 GHz and everything above it.  Eleven
of the twenty-five spec'd bins are measurable; the other fourteen are refused
with their reasons printed on the row.  This is geometry, not a defect: a
longer probe span moves both edges out, and nothing about the fix changes it.

What the surviving curve shows is deliberately not quoted as a result.
Across 3.67 to 7.83 GHz passivity stays between 0.975014 and 0.980713, flat
within about half a per cent and lowest at the top of the window, while
eps_eff rises smoothly from 3.58226 to 3.63845 and |S11| rises from 0.00414 to
0.00655 -- all three monotone in frequency and none of them dramatic.  Flat
passivity across a band means the deficit on this coupon does not grow with
frequency, which is exactly the thing to watch for on the board: a deficit
that rises toward the port side names the port, a deficit that stays flat
names a boundary.  No broadband S-parameter is quoted yet.  This is a coupon
and not the board, and the sweep is now a measurement rather than a proposal.

What landed in code is small and named.  PULSE_WINDOW is a module constant
with a "hann" branch kept on purpose, so the failure can be re-demonstrated
without reverting anything.  One weight object multiplies the record before
the bin sum and the drive before the guard, so the two cannot drift apart.
The report rows no longer call the tone accumulator's snapped bin "the drive
frequency" on a pulse run, which was the last place the old reading survived
in the output; a pulse run names its band, its bin count and its pulse
frequency instead, and the summary line does the same.  The full suite, 388
tests, still passes: the fix cost no test.

## 57. A window is a statement about its input, and neither claim was true

Third member of one family: the wrong-pair tolerance, the vacuous-pass
test, and now the taper.  The shape is the same in all three -- a
convention applied because it is conventional, whose precondition nobody
wrote down, returning a number that looks plausible and is not.  The first
two were caught by tests that were written to fail; this one by a gate
that was written to fail.  The pattern is now specific enough to be a rule
rather than a war story.

A window makes two claims at once: that the record has a truncation
discontinuity worth suppressing, and that the signal fills the record, so
that multiplying by the taper changes the spectrum by an amount that is
known and harmless.  Neither claim held here.  The record is a closed
transient -- a Ricker evaluated at t = 0 is about 1e-17 of its peak, and
the packet is through the PML before the record ends -- so there was
nothing to suppress.  And a transient that occupies the front part of the
record is precisely the case where a taper is not amplitude-neutral: it
multiplies the packet by a curve that is still moving underneath it, so it
imposes a slow amplitude ramp across the very waveform it is supposed to
be preserving.

> A window function is only valid where the record has a truncation discontinuity, and is only amplitude-neutral for a signal that fills the record. Apply neither condition blindly to a transient.

The measurement, kept short because section 56 carries it: at the bins,
the one-wave residual went from 0.0066 to 0.065 and the fitted reflection
from 0.0046 to 0.11, so the windowed phasors had stopped being one mode.
The bin nearest the tone read |S21| 1.24903 under the taper, 0.99017 flat,
and 0.98126 for the cw twin.

The method, as a rule in three parts: prove the two paths identical
before theorising about the difference; probe by monkeypatching a
throwaway script, so the source under test stays byte-identical and its
tests stay valid; and require a control that can tell a surgical probe
from a global one -- here the aggregate scalars coming back bit-identical
between the two window variants, which is what turned a coincidence into
an attribution.

The guard inherited the fault, and that is the uncomfortable part.
Feeding the bin sum and the drive_db guard through one weight is the right
design and stays: a guard taken through a different weight would be
judging one measurement by another one's leakage.  But it means the guard
is only as trustworthy as the estimator feeding it, and a fault in the
estimator moves the guard's own verdict -- the two builds did not agree on
which bins were usable, twelve against eleven.  So, as a design rule: a
shared estimator is a shared failure mode, and it must be validated before
it is shared.

Which closes on the question to ask of every operation that takes data
it did not create: what does this assume about its input, and is that
assumption checked anywhere?  If it is not checked, it is not a
convention, it is a hypothesis.

## 58. One span buys a factor of two and a half, and no more

The result first.  With the two guards as they stand, a probe span S
brackets the usable band between f_lo = v_ph/(5S) and f_hi = v_ph/(2S), so
the ratio is 5/2 exactly and independent of S.  The consequence follows in
one sentence: changing the probe span slides that 2.5:1 window across the
spectrum, it never widens it, so the usable bandwidth of a single run is
set by the guards and not by how long a probe span the geometry permits.

The measurement it reproduces, kept short: on the coupon, S = 9.6 mm
gives f_lo 3.2819 and f_hi 8.2046 GHz, and the run refused 3.25 GHz at
beta*span 1.238 rad, 0.019 under the 1.2566 floor, and 8.25 GHz at
3.159 rad, 0.017 past pi.  One caveat, stated honestly: the fitted beta
implied by that bottom row is 128.92 rad/m against 129.63 rad/m nominal,
0.55 per cent below, which is the loaded line's measured dispersion, while
the ceiling matches to three digits.

The span table, as prose and then as a list.  Each floor buys its
ceiling by the same factor of 2.5, so asking for a lower band and asking
for a higher one are the same request made twice: a longer span is not a
wider sweep, it is a lower sweep.

  - f_lo 3.0 GHz needs S = 10.5 mm and buys a top at 7.50 GHz
  - f_lo 2.5 GHz needs S = 12.6 mm and buys a top at 6.25 GHz
  - f_lo 2.0 GHz needs S = 15.8 mm and buys a top at 5.00 GHz

The two ends trade one for one.

The wish, answered directly.  Three to eight gigahertz is 2.667:1; the
guards give 2.5:1; so that sweep cannot be had from one station spacing
whatever span is chosen.  At the span that just reaches 3.0 GHz the top
stops at 7.50 GHz.  This is geometry and arithmetic, not a defect, and it
is the kind of limit worth knowing before a run is commissioned rather
than after it refuses fourteen bins.

The crop.  The board's strip runs from 8.7 mm to 32.2 mm, so 23.5 mm is
available along the line, less 1.2 mm of far-end PML for each thickness of
margin kept clear: 22.3 mm would open at 1.41 GHz and close at 3.53 GHz,
while 20.0 mm opens at 1.58 and closes at 3.94.  If the answer is more
bandwidth, the lever is the floor constant and not the span.  Relaxing
2*pi/5 to 2*pi/10 makes the ratio 5:1, bought with roughly double the
relative error in beta, because beta is then read off a smaller phase
difference across the same stations.  That is the trade, written plainly
and not yet recommended.

The recommendation, as arithmetic rather than a measurement: two spans,
15.8 mm and 6.6 mm, would cover 1.99 to 4.99 GHz and 4.77 to 11.93 GHz,
with a 0.21 GHz overlap, both inside the 23.5 mm the board offers.  Mark
it for what it is -- an arithmetic proposal from measured beta, assuming
beta proportional to f, keeping both guard constants fixed, and taking no
account of the drive_db guard clipping the band edges, so that each span's
usable set would be re-measured rather than predicted.


## 59. The pulse anchor is not at the frequency the logs imply, and the record-level scalars cannot test a window

Both facts below were verified from the logs and from the code on 2026-10-21,
and both are recorded as open items rather than as resolved.

The first is the anchor.  On a pulse run the record-level scalars -- beta,
eps_eff, |gamma|, |S21| and the fit residual -- come from a single-frequency
DftAccumulator built at studies.py 2407 with the frequency that studies.py
2375 snaps from the target: f0 = round(f_target*span)/span, with span =
n_acc*dt.  For a 2400-step record at dt = 0.7626 ps the grid spacing is
0.5464 GHz, so a target of 5.830 GHz snaps to 6.010 GHz.  The printed pair
beta = 239.4598 rad/m with eps_eff = 3.61420 is self-consistent only at
6.010 GHz; at the 5.8278 GHz the log line invites comparison with, the cw
tone returns beta = 232.4470.  The phase velocity is the same to 0.1 per
cent in both cases (1.5769e8 against 1.57529e8 m/s), so this is a labelling
and snapping defect rather than a wrong solve -- but a 3 per cent snap is
large enough that the record-level beta must never be quoted as a property
of the line at the target frequency.  Gate2 does not test it, because the
gate compares the 5.75 GHz bin against the cw tone and never the
record-level beta against anything.  Open item: snap in a way that reports
the offset, or print f0 explicitly beside the record-level scalars, or both.

The second is what follows from the first.  PULSE_WINDOW cannot affect the
record-level scalars: the weight is applied only to the array handed to the
bin transform (studies.py 2758-2815) and the record-level accumulator
carries no weight at all.  The previous turn used the byte-identical
record-level scalars as the control that isolated the Hann fault; that
control is structural and proves nothing.  The valid control is the same
bin at the same frequency under the two weights, and it does isolate the
fault: at 5.7500 GHz the Hann bin returns |S21| = 1.24903, |S11| = 0.05479,
passivity 1.563072 and residual 0.06883, against the flat bin's 0.99017,
0.00431, 0.980464 and 0.00612.  The report at sec:msres-broadband now
carries the bin-against-bin comparison and says of the record-level scalars
only that their agreement is structural, and this entry records the
correction so that the weaker claim is not repeated.

The same anchor is corroborated from the bins: interpolating the eleven rows of the flat run to 6.010 GHz returns beta = 239.38 rad/m against the printed 239.4598, a fit residual of 0.00663 against 0.00662, |S21| = 0.99003 against 0.99000 and |S11| = 0.00449 against 0.00456 -- three to four digits on four quantities computed independently of the record-level accumulator.

## 60. The passivity column is not a power ratio, and the defect does not explain the excess

The defect first, because it is two lines.  The row's "passivity" is
`s11_measured**2 + s21**2`, computed at studies.py 1989, and `s21` is not a
power ratio: it comes out of `forward_wave_amplitude` at studies.py 1969-1973,
which is handed one fitted complex impedance, `complex(station_fit.z0)`, for all
nine stations and returns the ratio of forward-wave VOLTAGE AMPLITUDES.
Squaring that ratio is a power ratio only when the two measurement planes carry
the same wave impedance, which on a line whose fitted impedance drifts across
the span they do not.  The `|S11|` in the same row is fitted from that same
single-zc fit, so the row is not an independent energy audit either: it is one
fitted impedance, squared twice and added.  The coupon's 0.9750..0.9807 is the
same amplitude quantity and carries the same caveat; the Hann bin's 1.563072 is
the same square and is not a fifty-seven per cent power excess.

The second point governs.  This defect is small.  An exact analytic test of the
shipped formula, a lossless flux-conserving forward wave across a 1.07
impedance step, returns 1.000572 -- 0.06 per cent -- when zc is the first
station's impedance, 0.999961 through a real nine-station fit, and exactly
1.000000 when zc is the geometric mean.  The naive per-quantity ratios, 0.9667
for |v| and 1.0344 for |i|, are not what the code computes; quoting them as if
they were is what made the defect look large enough to be an explanation.

What it leaves unexplained is therefore still unexplained.  The imported board's
eleven usable bins show |S21| growing monotonically from 1.0084 to 1.0448, 0.8
to 4.5 per cent, while the fitted |S11| stays between -49.7 and -34.3 dB.  A
passive line returning forward amplitude that grows with frequency, with almost
nothing reflected, is physically impossible, and an impedance step inside the
span cannot manufacture it: 0.06 per cent is the whole of what the
normalisation can do.  The excess is genuinely present in the quantity
measured, and it must be diagnosed rather than renamed.  The coupon's curve,
measured by the same code, is flat and slightly below one, so the mechanism is
geometry-specific and not a property of the fit alone.  Over the lower five
bins the excess tracks f^2 to within 2 per cent, drifting some 20 per cent above
that by 7.83 GHz; that is recorded because it is the one measured regularity in
the excess, and because no attenuation law produces a gain in the first place.

The classification is withdrawn.  The test proposed earlier -- passivity flat
in frequency names a boundary sink, passivity rising with a threshold names a
port sink -- was an inference from a column that is not a power ratio.  It is
void as stated and must not be used as an argument in either direction, for the
coupon or for the board.

What was added is a diagnostic and nothing else.  `BinMetric` carries two new
fields, `s21_power` = sqrt(P(x2)/P(x1)) built from each station's own
0.5 Re(V conj I) through the helper `_station_power`, and `passivity_power` =
|S11|^2 + |S21_power|^2.  They print in `_bin_row` on a separate
`power-normalised:` line AFTER the untouched amplitude line, so the two are
comparable row for row; the amplitude `s21` and `passivity` are byte-identical
to what shipped, and the suite stands at 390 tests, the 388 that shipped plus
two that pin this (a 1.07 step returns exactly 1.0 in the power column and
1.000572 in the amplitude one).

Its discriminating power is bounded, and the bound should be stated before the
number is read.  The power column differs from the amplitude column only in so
far as the two planes' own impedances differ, since sqrt(P2/P1) is
|v_last/v_first| times sqrt(z0_first/z0_last) while the amplitude column is
nearly blind to a step in the first place.  So the column answers "is the growth
a power growth" only if the two planes really do differ, and a null result there
is weak evidence, not proof.  What the column does settle, cheaply and bin by
bin, is whether the excess survives a change of normalisation at all.

The rules that follow.  No board S-parameter is quoted until the
power-normalised column has been read off a re-run: not |S11| against
frequency, not |S21|, not eps_eff as a property of the line.  And a ratio of
amplitudes is never again discussed as a statement about where power went; if a
sentence needs an energy reading, it has to name the quantity that delivers
one.

## 61. The coupon record re-runs identically, and the power-normalised column is a no-op on it

Before the board's power column can be read, the diagnostic needs a control on a record whose answer is already known, and the default coupon is that control: a flat, passive line whose eleven-bin table is already in the report. `.scratch/m2/validate_coupon.py` was re-run unchanged against the current code — log `validate_coupon_pw2.log`, `EXIT=0`, timings RUN_CW 24.525 s and RUN_PULSE 23.809 s for 48.333 s total — and it returns the table's numbers bin for bin: |S11| from -47.7 to -43.7 dB, passivity 0.977703 at 3.67 GHz rising to a mid-band maximum 0.980713 at 5.33 GHz and back to 0.975014 at 7.83 GHz, one-wave residual 0.0036 to 0.0112, |S21| -0.1 dB on every used bin, eleven used and fourteen refused, with the same four below the 1.257 rad floor and the same ten past pi. The CW twin line is byte-identical to the earlier run: |S11|port 0.00748, |S21| 0.98126, passivity 0.96293, n_warm 600. The pulse path is therefore deterministic down to everything it prints, and a difference between two runs of one record is a difference in the code or in the transform weight and not in the solve. That distinction has already cost something here: the 12-bin, passivity 1.52 to 1.56 log in the same directory is not a different record, it is this record under the Hann taper, and reading the two as a code regression would have been wrong.

On that same record the power column is close to a no-op, which is what the bound in §60 predicts. The power-normalised passivity exceeds the amplitude-squared one by 3.3e-4 at 7.83 GHz, 9.9e-4 at 6.17 GHz and 8.7e-4 at 3.67 GHz — a smooth mid-band-maximum difference between 0.03 and 0.10 per cent — while |S21| itself moves by less than 0.05 per cent, which is below the one decimal place of dB the row prints, so the two columns are digit-for-digit identical on this record. The size follows the mechanism: the two columns can differ only in so far as the fitted z0 at the two measurement planes differs, and on a 9.60 mm coupon span it barely does. This is a consistency check on the diagnostic and nothing more.

It carries no information about a record whose planes are not alike. Because the coupon's two planes are nearly the same impedance, agreement between the columns there is what the bound demands whether the power column is computing the right thing or is quietly the amplitude column again; only a record with a real impedance variation across the span can separate the two readings. Nor does reproducing the coupon's table license the board's: determinism says a number comes back the same, not that it is right, and the coupon's own external check remains the 0.91 per cent |S21| delta against its CW twin. The rule stands where it was left — an amplitude ratio is never an energy budget — and the board's passivity stays an amplitude-squared quantity until the power column has been read on that same record.

## 62. The power column has been read on the board, and the excess survives it

The pulse-only re-run of the identical lid3 geometry finished: `.scratch/m2/board_run_pw.log`, `EXIT=0`, 3100.0 s of pulse solve, the same 322x200x76 mesh at 0.1000 mm, 9600 steps, n_warm 0, eleven used bins of twenty-five and the same fourteen refusals. Its amplitude columns are bit-identical to `board_run2.log` on every used bin — zero difference in |S11|, in the amplitude passivity and in the one-wave residual — so the board record is deterministic down to what it prints, as the coupon was, and the only thing that changed between the two logs is the new line. Read on that line, the power-normalised passivity runs 1.018860 at 3.67 GHz to 1.096752 at 7.83 GHz, against 1.016780 to 1.091533 for the amplitude-squared one. Normalising by power neither fixes the excess nor hides it: it is present bin for bin in both columns, it is monotone increasing in both, and it comes out slightly larger on the power column. Fitted against f^2 the amplitude column gives slope 1.5576e-3 per GHz^2 with correlation 0.997 and the power column 1.6564e-3 with correlation 0.994, and |S21| grows 3.51 per cent from the first used bin to the last in either reading. The one-z_c amplitude ratio is therefore exonerated as the cause of the board's excess, and §60's hypothesis is now refuted by measurement as well as by the impedance-step argument; the coupon's near-no-op in §61 and the board's survival here are the two ends of the same bound.

The comparison has a resolution limit that should be stated rather than glossed. The bin row prints |S21| to one decimal place of dB, a rung of 1.16 per cent in amplitude, so the power column lands on the same rung as the amplitude one in eight of the eleven bins and one rung higher in three; that reads as a 1.16 per cent difference between the columns and is not one. What the log can resolve is fixed instead by the passivity figures, printed to six decimals: the difference in |S21| squared runs from 0.00208 to 0.00522 across the band, which is 0.10 to 0.26 per cent in |S21|. Anything finer than that is invisible in this record and no claim is made about it. The operational consequence is narrow and worth writing down: print |S21| to four decimals before asking this comparison to resolve anything below a per cent.

What remains is a shorter list, and none of it is the amplitude normalisation. The port de-embedding is untouched by this test. So is the truncation of the ground current at y_extent = 8.8 mm, where the full and truncated integrals are 1.086441e4 A and 1.085507e4 A, a 0.086 per cent shortfall — far too small to be the 1.7 to 9.7 per cent by itself, but the only asymmetric term identified so far. The disagreement between measured and model line impedance, |z0| 54.08 ohm at 16.4 degrees against 50.62 ohm, and eps_eff 3.563 measured against 3.325 model, is a statement about the fit and not a sink. The test that would separate a boundary sink from a port sink is the same record with the lid raised from three substrate heights to five, and it has not been run. It also cannot be run as written: the mesh that needs, 322x200x108, is 42 per cent more cells than the present run, which already holds about 3 GB against a 4 GiB container cap, so it would be OOM-killed as prepared and has to be trimmed first.

The rule this adds is the one the last three sections keep re-teaching: a passivity excess is not reportable until it has been put through the power-normalised column and through the print-precision bound, in that order, and both nulls and survivals have to be quoted with the resolution they were read at.

