# s11 phase investigation - 2026-11-04

Framing: this is an estimator audit, not a sign hunt. The premise "what single sign flip produces a 188.7535 deg offset" is FALSIFIED (section 1). The live finding is a candidate beta miswiring in the de-embed, and that finding is UNCONFIRMED (section 5).

## 1. Primary finding - the s11 block pairs two estimators

> gamma_port, the reflection moved to the port plane (emfit/studies.py:3266, declared at :1607; docstring :1527-1531).  Plane-independent: it does not move when the extraction plane moves.  modulus of B/A from fit_beta(n_wave=2), referred to z=0, plane-invariant at alpha=0, not de-embedded. phase_deg is unchanged and belongs to the one-wave station fit at the port plane, NOT to the magnitude beside it; no two-wave phase is reported because no two-wave beta is stored.
>
> Verbatim from leaf `/s11/basis` of `evidence/termination/build_A_50ohm_v3_zeff.json`; authored at `evidence/termination/run_build_A.py:1594-1602`.

`s11.magnitude` = 0.32556486641109117 is `s11_two_wave_mag`, the modulus of the TWO-wave B/A referred to z=0, and is NOT de-embedded: `evidence/termination/run_build_A.py:1392` `    s11_two_wave_mag = finite_or_none(abs(complex(res.gamma)))`, written at `:1589`. `s11.phase_deg` = -160.26362819520853 is `np.angle(s11)` with `evidence/termination/run_build_A.py:1386` `    s11 = complex(res.gamma_port)`, i.e. the ONE-wave station fit de-embedded to the port plane (`emfit/studies.py:3562-3565`), written at `:1591`.

Two estimators, two planes, one dict. The 188.7535 deg offset in `docs/design/complex_load_analysis_2026-11-04.md` section 3 was therefore computed by comparing objects from different pipelines: a port-plane one-wave phase against a quantity assembled from angle(Gamma_TE) and a measured s21 phase. It is NOT a physical phase residual and NOT evidence of a sign error.

Error class: a coincidence was found and liked too much. The artefact's own basis string said all of this in one sentence, was read, and was not treated as authoritative. Nothing was hidden; the file said so.

## 2. Sign audit - four sites at HEAD

### 2.1 i_cut and i_stations negation - AGREE
`emfit/studies.py:3355` `        i_cut = -complex(cut_spec[1])`, with `emfit/studies.py:3350-3354`: "``i_cut`` takes the station currents' negation -- the ground return is summed antiparallel to the trace current." and "...negating it refers the station impedance to the forward current." Physics requires the sign: the ground return flows antiparallel to the trace current, so raw V/I carries a spurious 180 deg. Documented convention, correctly applied.

### 2.2 deembed_reflection exponent - AGREE
`emfit/ports.py:1702-1703` `out = np.asarray(gamma, dtype=complex) * np.exp(` / `        -2j * complex(beta) * float(distance))`, against the module convention at `emfit/ports.py:1682-1684`: forward wave `exp(-1j * beta * x)`, "the reflection coefficient on the plane ``x`` is ``(B / A) exp(2j beta x)``". Moving a reflection upstream by d multiplies by exp(-2j*beta*d). Correct as written.

### 2.3 gamma_v = amp_v[1]/amp_v[0] = B/A - AGREE
`emfit/ports.py:1517-1518` `gamma_v = complex(amp_v[1] / amp_v[0])` / `gamma_i = complex(amp_i[1] / amp_i[0])`; `emfit/ports.py:783` "gamma: ``B / A``, so ``abs(gamma)`` is the reflection coefficient". The reflection is backward over forward amplitude. Correct.

### 2.4 _project_mode conjugation - UNVERIFIED
`emfit/studies.py:2351` `def _project_mode(field_edges, mode_edges):`; docstring `emfit/studies.py:2353-2355` gives ``sum(f * m) / sum(m * m)`` with no conjugate shown; `tests/test_studies.py:2006` `assert np.isrealobj(studies._project_mode(np.ones(4), np.ones(4)))` passes for real inputs either way. The executable body line was never quoted in any pass, so the conjugate question is OPEN and cannot be graded here.

### 2.5 Writer lines - section 1 reached from the code side
`evidence/termination/run_build_A.py:1386` `    s11 = complex(res.gamma_port)` and `:1392` `    s11_two_wave_mag = finite_or_none(abs(complex(res.gamma)))`: magnitude and phase are read from two different objects before either is written.

## 3. The beta substitution [HYPOTHESIS]

Everything in this section is stated at the PORT plane, `x = x_port = 0.0032 m`. That is a choice of comparison plane, not a finding, and none of the numbers below transfer to another plane without redoing the propagation.

The propagator convention, written once: moving toward the port multiplies by `exp(-2j*beta*d)`, so the phase SUBTRACTS `2*beta*d` (`emfit/ports.py:1702-1703`). The recorded `s11.phase_deg = -160.2636` is already de-embedded with `beta_one` over `d_station = 0.0072 m`. Removing that de-embed returns the station-plane value `+76.0000`; substituting a different beta requires that step first, or the result passes through the 360 deg wrap and comes out silently wrong.

Two candidate frames, differing only in where the analytic TE phase is referenced:

- **F1** - referenced to station 0, `x = 0.0104 m`, so `d_station = 0.0072 m` (18 cells; `MS_X_FIRST` at `emfit/studies.py:1178`).
- **F2** - referenced to the load, `x = 0.0200 m`, so `d_load = 0.0168 m`.

| frame | beta (rad/m) | propagated (deg) | TE at port | measured, re-de-embedded | residual |
|---|---|---|---|---|---|
| F1 | 286.3593 (one) | 236.2634 | 101.8340 | -160.2636 | -97.9024 |
| F1 | 231.5533 (two) | 191.0452 | 147.0522 | -115.0454 | -97.9024 |
| F2 | 286.3593 (one) | 551.2812 | 146.8162 | -160.2636 | -52.9202 |
| F2 | 231.5533 (two) | 445.7721 | -107.6747 | -115.0454 | +7.3707 |

**In F1 the substitution cancels.** Beta enters both legs with the same distance, so the residual is `-97.90` for either beta, and the s11 phase residual cannot see this defect at all in that frame. The substitution is observable only in F2, where the two legs carry different distances and it moves the residual from `-52.92` to `+7.37` - a swing of `2*(beta_one-beta_two)*(d_load-d_station) = 60.2909 deg`, exact.

F1 and F2 are separated solely by where the analytic TE phase is referenced. That is an assumption and not a computed fact, and it must be pinned by one line of the TE generator before the fix dispatch leans on the F2 number. The ambiguity is the dominant error term here: the `d_station` delta is `45.2182 deg` and the `d_load` delta `105.5091 deg`, both larger than the `52.92 deg` effect under test.

Frame-independent facts, true regardless of which frame holds: `2*(beta_one-beta_two)*d_station = +45.2182 deg` exactly, and `+105.5091 deg` over `d_load`. `beta_one = 286.3593` exceeds `beta_two = 231.5533` by 23.7% and `beta_model = 223.3531` by 28.2%. `beta = float(fit_one.beta)` at `emfit/studies.py:3387` feeds BOTH the s11 and the s21 de-embeds.

The s21 residual arithmetic is deliberately not rebuilt here: its de-embed appears to ADD its term where s11 SUBTRACTS, opposite in sign, which is unresolved and belongs to the s21 span defect in section 4.

## 4. Artefact defects - six, each with a reserved DR number

| DR | defect | evidence | severity |
|----|--------|----------|----------|
| DR-24 | s11.magnitude (two-wave) and s11.phase_deg (one-wave) mis-paired under one key | `run_build_A.py:1589-1591`; leaf `/s11/basis` | high |
| DR-25 | de-embed uses beta_one 286.3593 while the magnitude uses beta_two 231.5533 | `studies.py:3387`; leaves `/line/beta`, `/line/beta_two_wave` | high |
| DR-26 | s21.deembed_distance_m records 0.0072 but the operation used the 0.0172 span | leaves `/s21/deembed_distance_m`, `/geometry/s21_plane_index` | medium |
| DR-27 | s21 phase/raw basis strings describe the twin-reference branch that the run did not use | leaves `/s21/phase_deg_basis`, `/s21/raw_basis`, `/run/reference`, `/run/loaded_without_reference` | medium |
| DR-28 | meta.git_rev null, so no v3 artefact is tieable to a commit | leaf `/meta/git_rev` | medium |
| DR-29 | four z0 values in one artefact, and summary_line prints n/a for each it labels | leaves `/line/z0_re`, `/line/z0_im`, `/run/station_fit`, `z0_model`, TE 47.54 | medium |

DR-24: two estimators under one key is the defect that produced this investigation, and it gates AC-3 (leaf `/ac/AC-3/achieved/s11_abs` = 0.23216690987276836, the ONE-wave magnitude, while `/s11/magnitude` = 0.32556486641109117 - the gate grades a number the s11 block does not report).

DR-25: metadata that describes a de-embed cannot be trusted while the beta it used is a different fit from the beta that produced the magnitude; section 3 is the measurement of that gap.

DR-26: x_cut = 51 * 0.0004 = 0.0204 m and x_port = 8 * 0.0004 = 0.0032 m give 0.0172 m (derived), against a recorded 0.0072. The field is either the wrong distance or the wrong operation's name; a reader cannot tell which.

DR-27: `raw_basis` claims a 5.8 % difference against a value the same block records identically, and `phase_deg_basis` describes a twin-reference construction while `/run/reference` is null and `/run/loaded_without_reference` is true.

DR-28: without a revision, no defect above can be reproduced at the tree state that produced it.

DR-29: line.z0 = 42.43786214405251 - j15.727993189312496, station_fit.z0 = 44.207500737130495 + j0.3794459968505162, z0_model = 48.0987, TE 47.54 - four candidates, no arbitration, and summary_line prints n/a for each it labels.

DR-24..DR-29 are RESERVED by this document and are inserted into `docs/design/defect_register.md` by the s11-estimator-fix dispatch, because this dispatch's fence is one document.

## 5. Falsification test - pre-registered

One host run, same 50 ohm load, a SECOND `ix_port` so that d = station_x[0] - x_port changes (currently ix_port = 8, d = 0.0072 m; station_x[0] is pinned at MS_X_FIRST = 10.4e-3, so ix_port = 16 gives x_port = 0.0064, d = 0.0040, delta_d = -0.0032 m).

| observed move in s11.phase_deg | conclusion |
|--------------------------------|------------|
| 2*286.36*delta_d = -105.0 deg | de-embed is wired to beta_one; the fix is beta_two, section 3 survives |
| 2*231.55*delta_d = -84.9 deg | already beta_two; section 3 is FALSIFIED |
| neither | the phase pathway is mis-modelled in some other way; hypothesis dead |

Second observable, same run: `s21.phase_deg` is beta-dependent as beta*span, with span = 0.0204 - x_port changing with ix_port, so the run tests the pathway independently of s11. Two observables, one run. Null outcome, stated in advance: if the recorded s11 phase does not move with delta_d at either coefficient, section 3 is abandoned entirely and the phase pathway is re-opened from `emfit/studies.py:3562` onwards. The host command is authored by the engineer; this dispatch launches nothing.

## 6. Correction to complex_load_analysis_2026-11-04.md section 3

That document recorded the 188.7535 deg offset as "OPEN, no mechanism proposed". That status is now known to be overstated: the offset was computed on a one-wave port-plane phase set beside a two-wave magnitude, so the quantity compared does not exist in the model. Its section 3 stands as a record of what was computed, but its OPEN status is superseded by section 1 here: the mystery is smaller than recorded, not larger. This does NOT close the phase pathway - section 5 has not run, and section 3 remains a hypothesis.

Status: hypothesis unconfirmed. No code changed. No run performed. DR-24..DR-29 reserved, not yet in the register.
